"""Shared one-shot runtime for structured non-interactive agent CLIs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping, Protocol, Sequence
import uuid

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
)
from graphori_core.run_plan import NodeSpec, RunPlan

from .agent_contract import AgentTaskEnvelope, WorkerReport, worker_report_schema
from .provider_protocol import ProviderParseResult, ProviderProtocolError


class ProviderParser(Protocol):
    def parse(self, data: bytes) -> ProviderParseResult: ...


@dataclass(frozen=True)
class WorkspaceSnapshot:
    signatures: Mapping[str, str]
    head: str = ""


def _git_snapshot(workspace: Path) -> WorkspaceSnapshot:
    result = subprocess.run(
        ["git", "-C", str(workspace), "status", "--porcelain=v1", "-z",
         "--untracked-files=all"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise AdapterError(
            "startup_failure", "WorkspaceObservationUnavailable",
            "workspace changes cannot be observed safely",
        )
    records = result.stdout.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise AdapterError(
                "startup_failure", "WorkspaceObservationMalformed",
                "git workspace status was malformed",
            )
        status = record[:2]
        path = record[3:].decode("utf-8", errors="surrogateescape")
        if b"R" in status or b"C" in status:
            if index >= len(records):
                raise AdapterError(
                    "startup_failure", "WorkspaceObservationMalformed",
                    "git rename status was malformed",
                )
            path = records[index].decode("utf-8", errors="surrogateescape")
            index += 1
        if path != ".graphori" and not path.startswith(".graphori/"):
            paths.append(path)
    signatures: dict[str, str] = {}
    for relative in sorted(set(paths)):
        candidate = workspace / relative
        if candidate.is_file():
            signatures[relative] = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        elif candidate.exists():
            signatures[relative] = "present-non-file"
        else:
            signatures[relative] = "missing"
    head_result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    head = head_result.stdout.decode("ascii", errors="ignore").strip() \
        if head_result.returncode == 0 else ""
    return WorkspaceSnapshot(signatures, head)


def _workspace_delta(
        workspace: Path, before: WorkspaceSnapshot,
        after: WorkspaceSnapshot) -> tuple[str, ...]:
    paths = set(before.signatures) | set(after.signatures)
    changed = {
        path for path in paths if before.signatures.get(path) != after.signatures.get(path)
    }
    if before.head != after.head:
        if before.head and after.head:
            committed = subprocess.run(
                ["git", "-C", str(workspace), "diff", "--name-only", "-z",
                 before.head, after.head],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        else:
            committed = subprocess.run(
                ["git", "-C", str(workspace), "ls-files", "-z"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        if committed.returncode != 0:
            raise AdapterError(
                "outcome_unknown", "WorkspaceObservationUnavailable",
                "committed provider changes cannot be observed safely",
            )
        changed.update(
            path.decode("utf-8", errors="surrogateescape")
            for path in committed.stdout.split(b"\0") if path
        )
    return tuple(sorted(
        path for path in changed
        if path != ".graphori" and not path.startswith(".graphori/")
    ))


def _path_allowed(path: str, scopes: tuple[str, ...]) -> bool:
    normalized = path.replace(os.sep, "/").lstrip("./")
    for raw_scope in scopes:
        scope = raw_scope.replace(os.sep, "/").strip()
        if scope in {"", ".", "**", "**/*"}:
            return True
        scope = scope.rstrip("/")
        if normalized == scope or normalized.startswith(scope + "/"):
            return True
        if any(character in scope for character in "*?[") and fnmatch.fnmatch(normalized, scope):
            return True
    return False


@dataclass
class _Record:
    node: NodeSpec
    context: ContextBundle
    session_id: str
    runtime_id: str
    execution: ProcessExecution
    task: asyncio.Task[ProcessResult]
    queued_at: float
    baseline: WorkspaceSnapshot
    temp_dir: tempfile.TemporaryDirectory[str]
    result: ExecutionResult | None = None


class StructuredCliAdapter:
    """Common lifecycle for Codex and Claude Code one-shot CLI adapters."""

    provider = ""
    adapter_id = ""
    parser: ProviderParser
    required_help_tokens: tuple[str, ...] = ()

    def __init__(
            self, *, workspace_root: os.PathLike[str] | str,
            executable: Sequence[str] | None = None,
            max_concurrency: int = 2,
            supervisor: ProcessSupervisor | None = None,
            process_env: Mapping[str, str] | None = None,
            process_env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
            limits: ProcessLimits = ProcessLimits()) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.workspace_root = Path(workspace_root).resolve()
        self.executable = tuple(executable or (self.provider,))
        if not self.executable or any(not item for item in self.executable):
            raise ValueError("executable must contain explicit argv entries")
        self.max_concurrency = max_concurrency
        self.supervisor = supervisor or ProcessSupervisor()
        self.process_env = {
            "PYTHONDONTWRITEBYTECODE": "1",
            **dict(process_env or {}),
        }
        self.process_env_allowlist = process_env_allowlist
        self.limits = limits
        self._records: dict[str, _Record] = {}
        self._sessions: set[str] = set()
        self._probe: AdapterCapabilities | None = None
        self._cli_version = ""
        self._lock = asyncio.Lock()

    @property
    def active_handles(self) -> int:
        return len(self._records)

    def _help_argv(self) -> tuple[str, ...]:
        return (*self.executable, "--help")

    def _probe_result(self, available: bool, reason: str = "") -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            available=available,
            reason=reason,
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
            supports_usage=True,
            supports_files_modified=True,
            supports_structured_result=True,
            supports_nested_agents=False,
        )

    def probe(self) -> AdapterCapabilities:
        if self._probe is not None:
            return self._probe
        probe_limits = ProcessLimits(
            max_stdout_bytes=200_000, max_stderr_bytes=100_000,
            max_lines=5_000, timeout_seconds=10, grace_seconds=1,
        )
        try:
            version = self.supervisor.run(
                (*self.executable, "--version"), workspace_root=self.workspace_root,
                env=self.process_env, env_allowlist=self.process_env_allowlist,
                limits=probe_limits,
            )
            help_result = self.supervisor.run(
                self._help_argv(), workspace_root=self.workspace_root,
                env=self.process_env, env_allowlist=self.process_env_allowlist,
                limits=probe_limits,
            )
        except Exception:
            self._probe = self._probe_result(False, "provider CLI is unavailable")
            return self._probe
        self._cli_version = version.stdout.decode("utf-8", errors="replace").strip()
        help_text = help_result.stdout.decode("utf-8", errors="replace")
        missing = tuple(token for token in self.required_help_tokens if token not in help_text)
        if version.exit_code != 0 or help_result.exit_code != 0 or missing:
            self._probe = self._probe_result(
                False, "required CLI capability is unavailable"
                + (f": {', '.join(missing)}" if missing else ""),
            )
        else:
            self._probe = self._probe_result(True)
        return self._probe

    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle:
        return RuntimeRunHandle(self.adapter_id, f"{self.provider}-run:{plan.run_id}")

    async def start_session(self, node: NodeSpec) -> SessionHandle:
        session_id = f"{self.provider}-session:{node.node_id}:{uuid.uuid4().hex}"
        self._sessions.add(session_id)
        return SessionHandle(self.adapter_id, session_id)

    def _envelope(self, node: NodeSpec, context: ContextBundle) -> AgentTaskEnvelope:
        return AgentTaskEnvelope(
            task_id=node.node_id,
            attempt_id=context.attempt_id,
            team=node.team_id,
            role=node.role,
            objective=context.objective,
            constraints=tuple(context.acceptance_criteria),
            working_directory=".",
            read_scope=context.read_scope,
            write_scope=context.write_scope,
            verification_expectation=(
                "Report evidence; Do not claim verification PASS."
            ),
            requested_model=node.model,
            skill_bindings=context.skill_bindings,
        )

    def _command(
            self, envelope: AgentTaskEnvelope, schema_path: Path,
            node: NodeSpec) -> tuple[str, ...]:
        raise NotImplementedError

    async def dispatch(
            self, session: SessionHandle, node: NodeSpec,
            context: ContextBundle) -> DispatchHandle:
        if session.adapter_id != self.adapter_id or session.value not in self._sessions:
            raise ValueError("unknown provider adapter session")
        capabilities = self.probe()
        if not capabilities.available:
            raise AdapterError("startup_failure", "AdapterUnavailable", capabilities.reason)
        baseline = _git_snapshot(self.workspace_root)
        temp_dir = tempfile.TemporaryDirectory(prefix=f"graphori-{self.provider}-")
        schema_path = Path(temp_dir.name) / "worker-report-schema.json"
        schema_path.write_text(
            json.dumps(worker_report_schema(), sort_keys=True), encoding="utf-8",
        )
        runtime_id = f"{self.provider}:{uuid.uuid4().hex}"
        queued_at = self.supervisor.clock.monotonic()
        try:
            execution = await asyncio.to_thread(
                self.supervisor.start,
                self._command(self._envelope(node, context), schema_path, node),
                workspace_root=self.workspace_root,
                env=self.process_env,
                env_allowlist=self.process_env_allowlist,
                limits=self.limits,
            )
        except (MemoryError, KeyboardInterrupt, SystemExit):
            temp_dir.cleanup()
            raise
        except Exception as exc:
            temp_dir.cleanup()
            raise AdapterError(
                "startup_failure", type(exc).__name__, "provider CLI failed to start",
            ) from exc
        record = _Record(
            node=node, context=context, session_id=session.value, runtime_id=runtime_id,
            execution=execution,
            task=asyncio.create_task(asyncio.to_thread(self.supervisor.collect, execution)),
            queued_at=queued_at, baseline=baseline, temp_dir=temp_dir,
        )
        async with self._lock:
            if len(self._records) >= self.max_concurrency:
                self.supervisor.cancel(execution)
                temp_dir.cleanup()
                raise RuntimeError("adapter concurrency exhausted; scheduler must apply backpressure")
            self._records[runtime_id] = record
        return DispatchHandle(self.adapter_id, runtime_id, node.node_id)

    def _require(self, dispatch: DispatchHandle) -> _Record:
        if dispatch.adapter_id != self.adapter_id:
            raise ValueError("dispatch belongs to another adapter")
        try:
            return self._records[dispatch.value]
        except KeyError as exc:
            raise ValueError("unknown or already collected dispatch") from exc

    async def _normalize(self, record: _Record) -> ExecutionResult:
        if record.result is not None:
            return record.result
        normalize_started = self.supervisor.clock.monotonic()
        try:
            process = await asyncio.shield(record.task)
        except (MemoryError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            finished = self.supervisor.clock.monotonic()
            record.result = ExecutionResult(
                outcome="outcome_unknown", runtime_id=record.runtime_id,
                attempt_id=record.context.attempt_id, started_at=record.queued_at,
                finished_at=finished, error_kind=type(exc).__name__,
                error_detail="provider process supervision failed",
                total_attempt_ms=max(0, round((finished - record.queued_at) * 1000)),
                runtime_metadata=self._runtime_metadata(None, record.node.model),
            )
            return record.result

        parsed: ProviderParseResult | None = None
        protocol_error = ""
        try:
            parsed = self.parser.parse(process.stdout)
        except ProviderProtocolError as exc:
            protocol_error = str(exc)
        report: WorkerReport | None = parsed.report if parsed else None
        after = _git_snapshot(self.workspace_root)
        observed = _workspace_delta(self.workspace_root, record.baseline, after)
        violations = tuple(
            path for path in observed if not _path_allowed(path, record.context.write_scope)
        )
        if violations:
            outcome = "scope_violation"
            error_kind = "WriteScopeViolation"
            error_detail = "provider modified files outside the declared write scope"
        elif process.cancelled:
            outcome, error_kind, error_detail = "cancelled", "", ""
        elif process.timed_out:
            outcome, error_kind, error_detail = "timed_out", "", ""
        elif process.exit_code not in {0, None}:
            outcome, error_kind, error_detail = "failed", "", ""
        elif protocol_error or report is None:
            outcome = "incomplete_result"
            error_kind = "ProviderProtocolError" if protocol_error else "MissingWorkerReport"
            error_detail = protocol_error or "provider did not return a structured WorkerReport"
        elif report.status == "succeeded":
            outcome, error_kind, error_detail = "succeeded", "", ""
        else:
            outcome, error_kind, error_detail = "failed", "", ""
        stdout_digest = "sha256:" + hashlib.sha256(process.stdout).hexdigest()
        stderr_digest = "sha256:" + hashlib.sha256(process.stderr).hexdigest()
        metadata = self._runtime_metadata(parsed, record.node.model)
        metadata.update({
            "worker_report_status": report.status if report else "missing",
            "usage_status": "known" if parsed and parsed.usage else "unknown",
            "scope_violations": list(violations),
            "provider_start_ms": max(
                0, round(((process.first_stdout_at or process.finished_at)
                          - process.started_at) * 1000),
            ),
            "first_event_ms": max(
                0, round(((process.first_stdout_at or process.finished_at)
                          - process.started_at) * 1000),
            ),
            "worker_report_ms": max(
                0, round(((process.last_stdout_at or process.finished_at)
                          - process.started_at) * 1000),
            ),
        })
        normalized_at = self.supervisor.clock.monotonic()
        record.result = ExecutionResult(
            outcome=outcome,
            summary=report.summary if report else "",
            files_modified=observed,
            reported_files_modified=report.files_modified if report else (),
            open_risks=report.limitations if report else (),
            runtime_metadata=metadata,
            runtime_id=record.runtime_id,
            attempt_id=record.context.attempt_id,
            exit_code=process.exit_code,
            timed_out=process.timed_out,
            cancelled=process.cancelled,
            started_at=process.started_at,
            finished_at=process.finished_at,
            stdout_digest=stdout_digest,
            stderr_digest=stderr_digest,
            stdout_truncated=process.stdout_truncated,
            stderr_truncated=process.stderr_truncated,
            error_kind=error_kind,
            error_detail=error_detail,
            adapter_start_ms=max(0, round((process.started_at - record.queued_at) * 1000)),
            queue_wait_ms=max(0, round((process.started_at - record.queued_at) * 1000)),
            execution_ms=max(0, round((process.finished_at - process.started_at) * 1000)),
            collect_ms=max(0, round((normalized_at - normalize_started) * 1000)),
            total_attempt_ms=max(0, round((process.finished_at - record.queued_at) * 1000)),
        )
        return record.result

    def _runtime_metadata(
            self, parsed: ProviderParseResult | None,
            requested_model: str = "") -> dict[str, Any]:
        return {
            "provider": self.provider,
            "adapter": self.adapter_id,
            "adapter_protocol": 1,
            "cli_version": self._cli_version,
            "capability_snapshot": {
                "structured_result": True,
                "cancel": True,
                "reconcile": False,
                "persistent_session": False,
                "nested_agents": False,
            },
            "observed_model": parsed.observed_model if parsed else "",
            "requested_model": requested_model,
            "session_id": parsed.session_id if parsed else "",
            "usage": dict(parsed.usage) if parsed else {},
            "provider_reported_cost_usd": (
                parsed.provider_reported_cost_usd if parsed else None
            ),
        }

    async def events(self, dispatch: DispatchHandle):
        record = self._require(dispatch)
        result = await self._normalize(record)
        actor = "verifier" if record.node.kind == "verifier" else "worker"
        payload: dict[str, Any] = {
            "outcome": result.outcome,
            "summary": result.summary,
            "evidence_ids": list(result.evidence_ids),
            "open_risks": list(result.open_risks),
            "runtime_id": result.runtime_id,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "cancelled": result.cancelled,
            "stdout_digest": result.stdout_digest,
            "stderr_digest": result.stderr_digest,
            "files_modified": list(result.files_modified),
            "reported_files_modified": list(result.reported_files_modified),
            "runtime_metadata": dict(result.runtime_metadata),
        }
        if result.error_kind:
            payload["error_kind"] = result.error_kind
        if result.error_detail:
            payload["error_detail"] = result.error_detail
        yield RuntimeEvent(
            "worker_finished", record.node.node_id, actor, payload,
            event_id=f"{self.provider}:{record.runtime_id}:finished",
            producer_event_id=f"{self.provider}:{record.runtime_id}:finished",
        )

    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None:
        del reason
        await asyncio.to_thread(self.supervisor.cancel, self._require(dispatch).execution)

    async def collect(self, dispatch: DispatchHandle) -> ExecutionResult:
        record = self._require(dispatch)
        result = await self._normalize(record)
        cleanup_started = self.supervisor.clock.monotonic()
        async with self._lock:
            self._records.pop(dispatch.value, None)
        record.temp_dir.cleanup()
        cleaned_at = self.supervisor.clock.monotonic()
        cleanup_ms = max(0, round((cleaned_at - cleanup_started) * 1000))
        metadata = dict(result.runtime_metadata)
        metadata["cleanup_ms"] = cleanup_ms
        result = replace(
            result,
            runtime_metadata=metadata,
            total_attempt_ms=max(
                result.total_attempt_ms,
                round((cleaned_at - record.queued_at) * 1000),
            ),
        )
        record.result = result
        return result

    async def release(self, session: SessionHandle) -> None:
        leftovers = [
            record for record in self._records.values() if record.session_id == session.value
        ]
        for record in leftovers:
            if not record.task.done():
                await asyncio.to_thread(self.supervisor.cancel, record.execution)
            try:
                await asyncio.shield(record.task)
            except (MemoryError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass
            async with self._lock:
                self._records.pop(record.runtime_id, None)
            record.temp_dir.cleanup()
        self._sessions.discard(session.value)
