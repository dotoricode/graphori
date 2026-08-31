"""Non-interactive local process adapter for the Graphori execution seam."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Mapping, Sequence
import uuid

from graphori_core.evidence import EvidenceStore
from graphori_core.ports import (
    AdapterCapabilities,
    AdapterError,
    ContextBundle,
    DispatchHandle,
    ExecutionResult,
    RuntimeEvent,
    RuntimeRunHandle,
    SessionHandle,
)
from graphori_core.process_supervisor import (
    DEFAULT_ENV_ALLOWLIST,
    ProcessExecution,
    ProcessLimits,
    ProcessResult,
    ProcessSupervisor,
    resolve_workspace_path,
)
from graphori_core.run_plan import NodeSpec, RunPlan


@dataclass(frozen=True)
class ProcessCommand:
    """One explicit, workspace-confined non-interactive command."""

    argv: tuple[str, ...]
    cwd: str = "."
    env: Mapping[str, str] = field(default_factory=dict)
    env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST
    limits: ProcessLimits = ProcessLimits()
    capture_evidence: bool = False
    verdict_file: str = ""
    verdict_from_exit: bool = False
    criterion_ids: tuple[str, ...] = ()
    permission_profile: str = "workspace_process"
    sandbox_profile: str = "none"
    network_policy: str = "inherited"
    verifier_identity: str = "generic-process-exit-v1"

    def __post_init__(self) -> None:
        if isinstance(self.argv, (str, bytes)) or not isinstance(self.argv, Sequence):
            raise ValueError("argv must be an explicit sequence of strings")
        normalized = tuple(self.argv)
        if not normalized or any(not isinstance(item, str) or not item for item in normalized):
            raise ValueError("argv must contain non-empty strings")
        object.__setattr__(self, "argv", normalized)
        criteria = tuple(self.criterion_ids)
        if any(not isinstance(item, str) or not item for item in criteria):
            raise ValueError("criterion_ids must contain non-empty strings")
        object.__setattr__(self, "criterion_ids", criteria)
        for name in (
            "permission_profile", "sandbox_profile", "network_policy",
            "verifier_identity",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")


@dataclass
class _DispatchRecord:
    node: NodeSpec
    command: ProcessCommand
    attempt_id: str
    runtime_id: str
    session_id: str
    queued_at: float
    execution: ProcessExecution | None = None
    task: asyncio.Task[ProcessResult] | None = None
    startup_result: ExecutionResult | None = None
    collected: ExecutionResult | None = None
    verdict_path: Path | None = None
    verdict_baseline: tuple[int, int, int, str] | None = None


class GenericProcessAdapter:
    """Run explicit argv commands through the existing process supervisor.

    The adapter owns asynchronous handles and result normalization. Process
    creation, path confinement, environment filtering, bounded output, and
    descendant cleanup stay local to :class:`ProcessSupervisor`.
    """

    adapter_id = "generic-process"

    def __init__(self, *, workspace_root: os.PathLike[str] | str,
                 commands: Mapping[str, ProcessCommand], max_concurrency: int = 2,
                 supervisor: ProcessSupervisor | None = None,
                 evidence_store: EvidenceStore | None = None) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.workspace_root = Path(workspace_root)
        self.commands = dict(commands)
        self.max_concurrency = max_concurrency
        self.supervisor = supervisor or ProcessSupervisor()
        self.evidence_store = evidence_store
        self._records: dict[str, _DispatchRecord] = {}
        self._sessions: set[str] = set()
        self._lock = asyncio.Lock()
        self._evidence_lock = threading.Lock()

    @property
    def active_handles(self) -> int:
        return len(self._records)

    def probe(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            available=True,
            max_concurrency=self.max_concurrency,
            supports_sessions=True,
            supports_cancel=True,
            supports_reconcile=False,
            supports_heartbeat=False,
            supports_progress=False,
            supports_worktree=False,
            supports_persistent_session=False,
            supports_questions=False,
            supports_gate=False,
            supports_usage=False,
            supports_files_modified=False,
        )

    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle:
        return RuntimeRunHandle(self.adapter_id, f"process-run:{plan.run_id}")

    async def start_session(self, node: NodeSpec) -> SessionHandle:
        value = f"process-session:{node.node_id}:{uuid.uuid4().hex}"
        self._sessions.add(value)
        return SessionHandle(self.adapter_id, value)

    async def dispatch(self, session: SessionHandle, node: NodeSpec,
                       context: ContextBundle) -> DispatchHandle:
        if session.adapter_id != self.adapter_id or session.value not in self._sessions:
            raise ValueError("unknown GenericProcessAdapter session")
        command = self.commands.get(node.node_id)
        if command is None:
            raise ValueError(f"no process command configured for node: {node.node_id}")
        runtime_id = f"process:{uuid.uuid4().hex}"
        dispatch = DispatchHandle(self.adapter_id, runtime_id, node.node_id)
        queued_at = self.supervisor.clock.monotonic()
        record = _DispatchRecord(
            node=node, command=command, attempt_id=context.attempt_id,
            runtime_id=runtime_id, session_id=session.value, queued_at=queued_at,
        )
        async with self._lock:
            if len(self._records) >= self.max_concurrency:
                raise RuntimeError("adapter concurrency exhausted; scheduler must apply backpressure")
            self._records[runtime_id] = record
        try:
            if command.verdict_file:
                record.verdict_path = resolve_workspace_path(
                    self.workspace_root, command.verdict_file,
                )
                if record.verdict_path.is_file():
                    raw = record.verdict_path.read_bytes()
                    stat = record.verdict_path.stat()
                    record.verdict_baseline = (
                        stat.st_mtime_ns, stat.st_ctime_ns, len(raw),
                        hashlib.sha256(raw).hexdigest(),
                    )
            execution = await asyncio.to_thread(
                self.supervisor.start,
                command.argv,
                workspace_root=self.workspace_root,
                cwd=command.cwd,
                env=command.env,
                env_allowlist=command.env_allowlist,
                limits=command.limits,
            )
        except (MemoryError, KeyboardInterrupt, SystemExit):
            async with self._lock:
                self._records.pop(runtime_id, None)
            raise
        except Exception as exc:
            async with self._lock:
                self._records.pop(runtime_id, None)
            raise AdapterError(
                "startup_failure", type(exc).__name__,
                "process start rejected or failed",
            ) from exc
        record.execution = execution
        record.task = asyncio.create_task(asyncio.to_thread(self.supervisor.collect, execution))
        return dispatch

    async def _process_result(self, record: _DispatchRecord) -> ProcessResult | None:
        if record.startup_result is not None:
            return None
        if record.task is None:
            raise RuntimeError("process dispatch has no collection task")
        try:
            return await asyncio.shield(record.task)
        except (MemoryError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            finished = self.supervisor.clock.monotonic()
            record.startup_result = ExecutionResult(
                outcome="outcome_unknown",
                runtime_id=record.runtime_id,
                attempt_id=record.attempt_id,
                started_at=record.queued_at,
                finished_at=finished,
                error_kind=type(exc).__name__,
                error_detail="process supervision failed",
                total_attempt_ms=max(0, round((finished - record.queued_at) * 1000)),
            )
            return None

    def _verdict_event(self, record: _DispatchRecord, process: ProcessResult) -> RuntimeEvent | None:
        if (record.command.verdict_from_exit and not process.timed_out
                and not process.cancelled):
            proof_status = "PROVEN" if process.exit_code == 0 else "FAILED"
            evidence = [
                f"deterministic:{process.exit_code}",
                f"subprocess:verifier-command:exit:{process.exit_code}",
            ]
            criterion_evidence = {
                item: {
                    "status": proof_status,
                    "evidence_ids": [
                        f"subprocess:criterion-command:{item}:exit:{process.exit_code}"
                    ],
                }
                for item in record.command.criterion_ids
            }
            return RuntimeEvent(
                "verdict_recorded", record.node.node_id, "verifier",
                {
                    "verdict": "pass" if process.exit_code == 0 else "revise",
                    "evidence_ids": evidence,
                    "criterion_evidence": criterion_evidence,
                },
                event_id=f"generic:{record.runtime_id}:verdict",
                producer_event_id=f"generic:{record.runtime_id}:verdict",
            )
        if not record.command.verdict_file or process.exit_code != 0 \
                or process.timed_out or process.cancelled:
            return None
        verdict_path = record.verdict_path
        if verdict_path is None:
            return None
        try:
            raw = verdict_path.read_bytes()
            stat = verdict_path.stat()
            signature = (
                stat.st_mtime_ns, stat.st_ctime_ns, len(raw), hashlib.sha256(raw).hexdigest(),
            )
            if signature == record.verdict_baseline:
                return None
            data = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError, TypeError):
            return None
        verdict = data.get("verdict") if isinstance(data, dict) else None
        if verdict not in {"pass", "revise", "reject", "inconclusive"}:
            return None
        evidence = data.get("evidence_ids", [])
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            return None
        criterion_evidence = data.get("criterion_evidence", {})
        if not isinstance(criterion_evidence, dict):
            return None
        # Running the verifier command in a supervised process proves only
        # that command's exit. It does not prove every acceptance criterion.
        # Criterion-level proof must be emitted explicitly by the verifier.
        process_evidence = f"subprocess:verifier-command:exit:{process.exit_code}"
        if process_evidence not in evidence:
            evidence = [*evidence, process_evidence]
        return RuntimeEvent(
            "verdict_recorded", record.node.node_id, "verifier",
            {"verdict": verdict, "evidence_ids": evidence,
             "criterion_evidence": criterion_evidence},
            event_id=f"generic:{record.runtime_id}:verdict",
            producer_event_id=f"generic:{record.runtime_id}:verdict",
        )

    async def events(self, dispatch: DispatchHandle):
        record = self._require_record(dispatch)
        process = await self._process_result(record)
        result = self._normalize(record, process)
        record.collected = result
        actor = "verifier" if record.node.kind == "verifier" else "worker"
        yield RuntimeEvent(
            "worker_finished", record.node.node_id, actor,
            self._worker_finished_payload(result),
            event_id=f"generic:{record.runtime_id}:finished",
            producer_event_id=f"generic:{record.runtime_id}:finished",
        )
        if process is not None and record.node.kind == "verifier":
            verdict = self._verdict_event(record, process)
            if verdict is not None:
                yield verdict

    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None:
        del reason
        record = self._require_record(dispatch)
        if record.execution is not None:
            await asyncio.to_thread(self.supervisor.cancel, record.execution)

    def _put_evidence(self, data: bytes, label: str) -> str:
        if not data or self.evidence_store is None:
            return ""
        with self._evidence_lock:
            return self.evidence_store.put(data, label=label)

    def _normalize(self, record: _DispatchRecord,
                   process: ProcessResult | None) -> ExecutionResult:
        if record.collected is not None:
            return record.collected
        if record.startup_result is not None:
            result = record.startup_result
        else:
            collect_started = self.supervisor.clock.monotonic()
            assert process is not None
            collected_at = self.supervisor.clock.monotonic()
            if process.cancelled:
                outcome = "cancelled"
            elif process.timed_out:
                outcome = "timed_out"
            elif process.exit_code == 0 or record.command.verdict_from_exit:
                outcome = "succeeded"
            else:
                outcome = "failed"
            stdout_digest = "sha256:" + hashlib.sha256(process.stdout).hexdigest()
            stderr_digest = "sha256:" + hashlib.sha256(process.stderr).hexdigest()
            stdout_evidence = ""
            stderr_evidence = ""
            if record.command.capture_evidence:
                stdout_evidence = self._put_evidence(
                    process.stdout, f"{record.attempt_id}:stdout",
                )
                stderr_evidence = self._put_evidence(
                    process.stderr, f"{record.attempt_id}:stderr",
                )
            evidence_ids = tuple(item for item in (stdout_evidence, stderr_evidence) if item)
            start_ms = max(0, round((process.started_at - record.queued_at) * 1000))
            execution_ms = max(0, round((process.finished_at - process.started_at) * 1000))
            collect_ms = max(0, round((collected_at - collect_started) * 1000))
            total_ms = max(0, round((collected_at - record.queued_at) * 1000))
            result = ExecutionResult(
                outcome=outcome,
                evidence_ids=evidence_ids,
                runtime_id=record.runtime_id,
                attempt_id=record.attempt_id,
                exit_code=process.exit_code,
                timed_out=process.timed_out,
                cancelled=process.cancelled,
                started_at=process.started_at,
                finished_at=process.finished_at,
                stdout_digest=stdout_digest,
                stderr_digest=stderr_digest,
                stdout_truncated=process.stdout_truncated,
                stderr_truncated=process.stderr_truncated,
                stdout_evidence_id=stdout_evidence,
                stderr_evidence_id=stderr_evidence,
                adapter_start_ms=start_ms,
                queue_wait_ms=start_ms,
                execution_ms=execution_ms,
                collect_ms=collect_ms,
                total_attempt_ms=total_ms,
            )
        return result

    @staticmethod
    def _worker_finished_payload(result: ExecutionResult) -> dict[str, object]:
        return {
            "outcome": result.outcome,
            "summary": result.summary,
            "runtime_id": result.runtime_id,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "cancelled": result.cancelled,
            "stdout_digest": result.stdout_digest,
            "stderr_digest": result.stderr_digest,
            "stdout_truncated": result.stdout_truncated,
            "stderr_truncated": result.stderr_truncated,
            "evidence_ids": list(result.evidence_ids),
            "open_risks": list(result.open_risks),
            "metrics": {
                "adapter_start_ms": result.adapter_start_ms,
                "queue_wait_ms": result.queue_wait_ms,
                "execution_ms": result.execution_ms,
                "collect_ms": result.collect_ms,
                "total_attempt_ms": result.total_attempt_ms,
            },
            **({"error_kind": result.error_kind} if result.error_kind else {}),
            **({"error_detail": result.error_detail} if result.error_detail else {}),
        }

    async def collect(self, dispatch: DispatchHandle) -> ExecutionResult:
        record = self._require_record(dispatch)
        if record.collected is None:
            process = await self._process_result(record)
            record.collected = self._normalize(record, process)
        result = record.collected
        async with self._lock:
            self._records.pop(dispatch.value, None)
        return result

    async def release(self, session: SessionHandle) -> None:
        leftovers = [
            record for record in self._records.values()
            if record.session_id == session.value
        ]
        for record in leftovers:
            if record.execution is not None and record.task is not None \
                    and not record.task.done():
                await asyncio.to_thread(self.supervisor.cancel, record.execution)
            if record.task is not None:
                try:
                    await asyncio.shield(record.task)
                except (MemoryError, KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    pass
            async with self._lock:
                self._records.pop(record.runtime_id, None)
        self._sessions.discard(session.value)

    def _require_record(self, dispatch: DispatchHandle) -> _DispatchRecord:
        if dispatch.adapter_id != self.adapter_id:
            raise ValueError("dispatch belongs to another adapter")
        try:
            return self._records[dispatch.value]
        except KeyError as exc:
            raise ValueError("unknown or already collected dispatch") from exc
