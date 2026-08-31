"""Overlap an explicitly repeatable verifier with a running worker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import tempfile
import time
from typing import Mapping
import uuid

from graphori_core.ports import (
    AdapterCapabilities, ContextBundle, DispatchHandle, ExecutionAdapter,
    ExecutionResult, RuntimeEvent, RuntimeRunHandle, SessionHandle,
)
from graphori_core.proof_action import (
    INCOMPLETE, ProofActionKey, build_proof_action_key,
)
from graphori_core.proof_adoption import ProofAdopter, ProofCandidate
from graphori_core.process_supervisor import ProcessResult, ProcessSupervisor
from graphori_core.run_plan import NodeSpec, RunPlan
from graphori_core.workspace_snapshot import (
    copy_workspace as _copy_workspace,
    workspace_digest,
)

from .generic.adapter import ProcessCommand


@dataclass(frozen=True)
class _CandidateRecord:
    candidate: ProofCandidate
    action_key: ProofActionKey
    process: ProcessResult


@dataclass(frozen=True)
class _Session:
    inner: SessionHandle
    node: NodeSpec


@dataclass(frozen=True)
class _Dispatch:
    inner: DispatchHandle | None
    node: NodeSpec
    attempt_id: str
    proof: _CandidateRecord | None = None


@dataclass
class _Metrics:
    speculative_attempts: int = 0
    complete_action_keys: int = 0
    pass_candidates: int = 0
    pass_reuses: int = 0
    fallbacks: int = 0


def _proof_ids(verifier_id: str, command: ProcessCommand) -> tuple[str, ...]:
    return tuple(sorted(set(command.criterion_ids))) or (f"node:{verifier_id}",)


class LiveVerifyAdapter:
    """Speculatively run repeatable verification and reuse only exact proofs.

    The durable engine and its journal remain authoritative. A speculative
    result is merely a performance hint until the verifier Node is dispatched,
    the worker has finished, and the current workspace digest exactly matches
    the digest sealed with the result. Any uncertainty falls back to the
    wrapped v2 execution path.
    """

    adapter_id = "live-verify"

    def __init__(self, inner: ExecutionAdapter, *, workspace_root: Path | str,
                 commands: Mapping[str, ProcessCommand], poll_seconds: float = 0.025,
                 settle_seconds: float = 0.1,
                 supervisor: ProcessSupervisor | None = None) -> None:
        if poll_seconds <= 0 or settle_seconds < 0:
            raise ValueError("live verification intervals must be non-negative")
        self.inner = inner
        self.workspace_root = Path(workspace_root).resolve()
        self.commands = dict(commands)
        self.poll_seconds = poll_seconds
        self.settle_seconds = settle_seconds
        self.supervisor = supervisor or ProcessSupervisor()
        self._sessions: dict[str, _Session] = {}
        self._dispatches: dict[str, _Dispatch] = {}
        self._verifier_for_worker: dict[str, str] = {}
        self._watchers: dict[str, asyncio.Task[None]] = {}
        self._stop: dict[str, asyncio.Event] = {}
        self._proofs: dict[str, _CandidateRecord] = {}
        self._pending_fallback: dict[str, str] = {}
        self._fallback_reasons: dict[str, int] = {}
        self._metrics = _Metrics()

    def metrics(self) -> dict[str, object]:
        attempts = self._metrics.speculative_attempts
        candidates = self._metrics.pass_candidates
        return {
            "live_verify_attempt_count": attempts,
            "live_verify_eligible_count": self._metrics.complete_action_keys,
            "live_verify_eligible_rate": (
                self._metrics.complete_action_keys / attempts if attempts else 0.0
            ),
            "live_verify_pass_candidate_count": candidates,
            "live_verify_reuse_count": self._metrics.pass_reuses,
            "live_verify_reuse_rate": (
                self._metrics.pass_reuses / candidates if candidates else 0.0
            ),
            "live_verify_fallback_count": self._metrics.fallbacks,
            "live_verify_fallback_reasons": dict(sorted(self._fallback_reasons.items())),
        }

    def _fallback(self, verifier_id: str, reason: str) -> None:
        self._pending_fallback[verifier_id] = reason

    def _record_fallback(self, verifier_id: str) -> None:
        reason = self._pending_fallback.pop(verifier_id, "no_pass_candidate")
        self._metrics.fallbacks += 1
        self._fallback_reasons[reason] = self._fallback_reasons.get(reason, 0) + 1

    def _action_key(self, verifier_id: str, command: ProcessCommand, *,
                    root: Path, input_digest: str) -> ProofActionKey:
        return build_proof_action_key(
            workspace_root=root,
            proof_ids=_proof_ids(verifier_id, command),
            argv=command.argv,
            cwd=command.cwd,
            input_digest=input_digest,
            env=command.env,
            env_allowlist=command.env_allowlist,
            permission_profile=command.permission_profile,
            sandbox_profile=command.sandbox_profile,
            network_policy=command.network_policy,
            verifier_identity=command.verifier_identity,
        )

    def probe(self) -> AdapterCapabilities:
        capability = self.inner.probe()
        return AdapterCapabilities(
            self.adapter_id, capability.available,
            max_concurrency=capability.max_concurrency,
            supports_cancel=capability.supports_cancel,
            supports_usage=capability.supports_usage,
            supports_files_modified=capability.supports_files_modified,
            supports_structured_result=capability.supports_structured_result,
            reason=capability.reason, authentication=capability.authentication,
        )

    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle:
        self._verifier_for_worker.clear()
        self._proofs.clear()
        self._pending_fallback.clear()
        self._fallback_reasons.clear()
        self._metrics = _Metrics()
        for node in plan.nodes:
            if node.kind == "verifier" and node.node_id in self.commands:
                for dependency in node.dependencies:
                    self._verifier_for_worker[dependency] = node.node_id
        inner = await self.inner.prepare_run(plan)
        return RuntimeRunHandle(self.adapter_id, inner.value)

    async def start_session(self, node: NodeSpec) -> SessionHandle:
        inner = await self.inner.start_session(node)
        value = f"live-session:{uuid.uuid4().hex}"
        self._sessions[value] = _Session(inner, node)
        return SessionHandle(self.adapter_id, value)

    async def _watch(self, worker_id: str, verifier_id: str, initial: str) -> None:
        stop = self._stop[worker_id]
        observed = initial
        changed_at: float | None = None
        while not stop.is_set():
            await asyncio.sleep(self.poll_seconds)
            current = await asyncio.to_thread(workspace_digest, self.workspace_root)
            if current != observed:
                observed = current
                changed_at = time.monotonic()
                continue
            if current == initial or changed_at is None:
                continue
            if time.monotonic() - changed_at < self.settle_seconds:
                continue
            command = self.commands[verifier_id]
            self._metrics.speculative_attempts += 1
            with tempfile.TemporaryDirectory(prefix="graphori-live-verify-") as directory:
                snapshot = Path(directory) / "workspace"
                try:
                    await asyncio.to_thread(_copy_workspace, self.workspace_root, snapshot)
                    snapshot_digest = await asyncio.to_thread(workspace_digest, snapshot)
                    source_digest = await asyncio.to_thread(
                        workspace_digest, self.workspace_root,
                    )
                    if snapshot_digest != source_digest:
                        self._fallback(verifier_id, "source_snapshot_mismatch")
                        observed = source_digest
                        changed_at = time.monotonic()
                        continue
                    action_key_before = await asyncio.to_thread(
                        self._action_key, verifier_id, command,
                        root=snapshot, input_digest=source_digest,
                    )
                    if action_key_before.eligibility == INCOMPLETE:
                        reason = action_key_before.incomplete_reasons[0]
                        self._fallback(verifier_id, f"incomplete_action_key:{reason}")
                        return
                    self._metrics.complete_action_keys += 1
                    process = await asyncio.to_thread(
                        self.supervisor.run, command.argv,
                        workspace_root=snapshot, cwd=command.cwd,
                        env=command.env, env_allowlist=command.env_allowlist,
                        limits=command.limits,
                    )
                    unchanged_snapshot = (
                        await asyncio.to_thread(workspace_digest, snapshot)
                        == snapshot_digest
                    )
                    action_key_after = await asyncio.to_thread(
                        self._action_key, verifier_id, command,
                        root=snapshot, input_digest=source_digest,
                    )
                except (OSError, ValueError):
                    self._fallback(verifier_id, "execution_envelope_unavailable")
                    return
            after = await asyncio.to_thread(workspace_digest, self.workspace_root)
            if action_key_after.eligibility == INCOMPLETE:
                self._fallback(verifier_id, "action_key_became_incomplete")
            elif (action_key_before.entry_executable_identity
                  != action_key_after.entry_executable_identity):
                self._fallback(verifier_id, "entry_executable_changed")
            elif action_key_before.digest() != action_key_after.digest():
                self._fallback(verifier_id, "execution_envelope_changed")
            elif not unchanged_snapshot:
                self._fallback(verifier_id, "snapshot_changed")
            elif source_digest != after:
                self._fallback(verifier_id, "source_changed")
            elif process.exit_code != 0 or process.timed_out or process.cancelled:
                self._fallback(verifier_id, "verifier_did_not_pass")
            else:
                evidence_refs = tuple(
                    f"subprocess:criterion-command:{item}:exit:0"
                    for item in _proof_ids(verifier_id, command)
                )
                candidate = ProofCandidate(
                    proof_ids=_proof_ids(verifier_id, command),
                    source_digest=source_digest,
                    action_schema=action_key_before.schema,
                    action_digest=action_key_before.digest(),
                    evidence_refs=evidence_refs,
                    verdict="pass",
                )
                self._proofs[verifier_id] = _CandidateRecord(
                    candidate, action_key_before, process,
                )
                self._metrics.pass_candidates += 1
                self._pending_fallback.pop(verifier_id, None)
            observed = after
            changed_at = None

    async def dispatch(self, session: SessionHandle, node: NodeSpec,
                       context: ContextBundle) -> DispatchHandle:
        route = self._sessions.get(session.value)
        if session.adapter_id != self.adapter_id or route is None or route.node != node:
            raise ValueError("unknown live verification session")
        if node.kind == "verifier" and node.node_id in self.commands:
            for worker_id, verifier_id in self._verifier_for_worker.items():
                if verifier_id != node.node_id:
                    continue
                stop = self._stop.get(worker_id)
                if stop is not None:
                    stop.set()
                watcher = self._watchers.get(worker_id)
                if watcher is not None:
                    try:
                        await watcher
                    except Exception:
                        self._proofs.pop(node.node_id, None)
                self._watchers.pop(worker_id, None)
                self._stop.pop(worker_id, None)
            proof = self._proofs.get(node.node_id)
            if proof is not None:
                try:
                    current = await asyncio.to_thread(workspace_digest, self.workspace_root)
                except (OSError, ValueError):
                    current = ""
                if not current:
                    self._fallback(node.node_id, "adoption_source_unavailable")
                else:
                    adoption_key = await asyncio.to_thread(
                        self._action_key, node.node_id, self.commands[node.node_id],
                        root=self.workspace_root, input_digest=current,
                    )
                    decision = ProofAdopter.decide(
                        proof.candidate,
                        current_source_digest=current,
                        current_action_key=adoption_key,
                    )
                    if decision.adopted:
                        value = f"live-dispatch:{uuid.uuid4().hex}"
                        self._dispatches[value] = _Dispatch(
                            None, node, context.attempt_id, proof,
                        )
                        self._metrics.pass_reuses += 1
                        self._pending_fallback.pop(node.node_id, None)
                        return DispatchHandle(self.adapter_id, value, node.node_id)
                    self._fallback(node.node_id, f"adoption_{decision.reason}")
            self._record_fallback(node.node_id)
        verifier_id = self._verifier_for_worker.get(node.node_id)
        initial = ""
        if verifier_id is not None:
            try:
                initial = await asyncio.to_thread(workspace_digest, self.workspace_root)
            except (OSError, ValueError):
                verifier_id = None
        inner = await self.inner.dispatch(route.inner, node, context)
        value = f"live-dispatch:{uuid.uuid4().hex}"
        self._dispatches[value] = _Dispatch(inner, node, context.attempt_id)
        if verifier_id is not None:
            stop = asyncio.Event()
            self._stop[node.node_id] = stop
            self._watchers[node.node_id] = asyncio.create_task(
                self._watch(node.node_id, verifier_id, initial),
            )
        return DispatchHandle(self.adapter_id, value, node.node_id)

    def _dispatch(self, dispatch: DispatchHandle) -> _Dispatch:
        if dispatch.adapter_id != self.adapter_id or dispatch.value not in self._dispatches:
            raise ValueError("unknown live verification dispatch")
        return self._dispatches[dispatch.value]

    @staticmethod
    def _result(route: _Dispatch) -> ExecutionResult:
        assert route.proof is not None
        process = route.proof.process
        elapsed_ms = max(0, round((process.finished_at - process.started_at) * 1000))
        return ExecutionResult(
            outcome="succeeded", runtime_id=f"live-proof:{route.node.node_id}",
            attempt_id=route.attempt_id, exit_code=process.exit_code,
            started_at=process.started_at, finished_at=process.finished_at,
            execution_ms=elapsed_ms, total_attempt_ms=elapsed_ms,
            runtime_metadata={"live_verify_reused": True,
                              "proof_source": "immutable_snapshot",
                              "workspace_digest": route.proof.candidate.source_digest,
                              "proof_action_schema": route.proof.action_key.schema,
                              "proof_action_digest": route.proof.action_key.digest(),
                              "proof_candidate_digest": route.proof.candidate.digest(),
                              "proof_adoption": "candidate_adopted"},
        )

    async def events(self, dispatch: DispatchHandle):
        route = self._dispatch(dispatch)
        if route.proof is None:
            assert route.inner is not None
            async for event in self.inner.events(route.inner):
                yield event
            return
        result = self._result(route)
        exit_code = route.proof.process.exit_code
        yield RuntimeEvent(
            "worker_finished", route.node.node_id, "verifier",
            {"outcome": "succeeded", "runtime_id": result.runtime_id,
             "attempt_id": route.attempt_id, "exit_code": exit_code,
             "runtime_metadata": dict(result.runtime_metadata)},
            event_id=f"live:{dispatch.value}:finished",
            producer_event_id=f"live:{dispatch.value}:finished",
        )
        status = "PROVEN" if exit_code == 0 else "FAILED"
        criteria = self.commands[route.node.node_id].criterion_ids
        yield RuntimeEvent(
            "verdict_recorded", route.node.node_id, "verifier",
            {"verdict": "pass" if exit_code == 0 else "revise",
             "evidence_ids": ["deterministic:0",
                              f"subprocess:verifier-command:exit:{exit_code}"],
             "verification_command": list(self.commands[route.node.node_id].argv),
             "verification_exit_code": exit_code,
             "workspace_digest": route.proof.candidate.source_digest,
             "criterion_evidence": {
                 item: {"status": status, "evidence_ids": [
                     f"subprocess:criterion-command:{item}:exit:{exit_code}"
                 ]} for item in criteria
             }},
            event_id=f"live:{dispatch.value}:verdict",
            producer_event_id=f"live:{dispatch.value}:verdict",
        )

    async def acknowledge(self, event: RuntimeEvent) -> None:
        await self.inner.acknowledge(event)

    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None:
        route = self._dispatch(dispatch)
        stop = self._stop.get(route.node.node_id)
        if stop is not None:
            stop.set()
        if route.inner is not None:
            await self.inner.cancel(route.inner, reason)

    async def collect(self, dispatch: DispatchHandle) -> ExecutionResult:
        route = self._dispatch(dispatch)
        try:
            if route.proof is not None:
                self._proofs.pop(route.node.node_id, None)
                return self._result(route)
            assert route.inner is not None
            result = await self.inner.collect(route.inner)
            if result.outcome != "succeeded":
                stop = self._stop.get(route.node.node_id)
                if stop is not None:
                    stop.set()
            return result
        finally:
            self._dispatches.pop(dispatch.value, None)

    async def release(self, session: SessionHandle) -> None:
        route = self._sessions.pop(session.value)
        await self.inner.release(route.inner)

    async def close_run(self, run_id: str) -> None:
        close_run = getattr(self.inner, "close_run", None)
        if callable(close_run):
            await close_run(run_id)
