"""Runtime ports used by the portable Graphori execution engine."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .run_plan import NodeSpec, RunPlan
from .skills import SkillBinding


class AdapterError(RuntimeError):
    """Sanitized expected failure at the execution-adapter seam."""

    def __init__(self, outcome: str, error_kind: str, detail: str = "") -> None:
        super().__init__(detail or error_kind)
        self.outcome = outcome
        self.error_kind = error_kind
        self.detail = detail


@dataclass(frozen=True)
class AdapterCapabilities:
    adapter_id: str
    available: bool
    max_parallelism: int = 1
    supports_sessions: bool = True
    supports_cancel: bool = True
    reason: str = ""
    authentication: str = "unknown"
    max_concurrency: int | None = None
    supports_reconcile: bool = False
    supports_heartbeat: bool = False
    supports_progress: bool = False
    supports_worktree: bool = False
    supports_persistent_session: bool = False
    supports_questions: bool = False
    supports_gate: bool = False
    supports_usage: bool = False
    supports_files_modified: bool = False
    supports_structured_result: bool = False
    supports_nested_agents: bool = False
    supports_delivery_ack: bool = False

    def __post_init__(self) -> None:
        if self.authentication not in {"ready", "not_ready", "unknown", "not_applicable"}:
            raise ValueError("authentication must be ready, not_ready, unknown, or not_applicable")
        if self.max_parallelism < 1:
            raise ValueError("max_parallelism must be at least 1")
        if self.max_concurrency is None:
            object.__setattr__(self, "max_concurrency", self.max_parallelism)
        else:
            if self.max_concurrency < 1:
                raise ValueError("max_concurrency must be at least 1")
            if self.max_parallelism != 1 and self.max_concurrency != self.max_parallelism:
                raise ValueError("max_concurrency conflicts with legacy max_parallelism")
            object.__setattr__(self, "max_parallelism", self.max_concurrency)


@dataclass(frozen=True)
class RuntimeRunHandle:
    adapter_id: str
    value: str


@dataclass(frozen=True)
class SessionHandle:
    adapter_id: str
    value: str


@dataclass(frozen=True)
class DispatchHandle:
    adapter_id: str
    value: str
    node_id: str


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    node_id: str
    actor_role: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = ""
    producer_event_id: str = ""
    actor_role_id: str = ""
    occurred_at: str = ""


@dataclass(frozen=True)
class ContextBundle:
    objective: str
    attempt_id: str = ""
    acceptance_criteria: tuple[str, ...] = ()
    read_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    selected_skills: tuple[str, ...] = ()
    skill_bindings: tuple[SkillBinding, ...] = ()
    evidence_requirements: tuple[str, ...] = ()

    @classmethod
    def from_node(cls, node: NodeSpec) -> "ContextBundle":
        return cls(
            objective=node.objective,
            acceptance_criteria=node.acceptance_criteria,
            read_scope=node.read_scope,
            write_scope=node.write_scope,
            selected_skills=node.skills,
            skill_bindings=node.skill_bindings,
            evidence_requirements=node.evidence_requirements,
        )


@dataclass(frozen=True)
class ExecutionResult:
    outcome: str
    summary: str = ""
    evidence_ids: tuple[str, ...] = ()
    files_modified: tuple[str, ...] = ()
    reported_files_modified: tuple[str, ...] = ()
    open_risks: tuple[str, ...] = ()
    runtime_metadata: Mapping[str, Any] = field(default_factory=dict)
    runtime_id: str = ""
    attempt_id: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    cancelled: bool = False
    started_at: float | None = None
    finished_at: float | None = None
    stdout_digest: str = ""
    stderr_digest: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    stdout_evidence_id: str = ""
    stderr_evidence_id: str = ""
    error_kind: str = ""
    error_detail: str = ""
    adapter_start_ms: int = 0
    queue_wait_ms: int = 0
    execution_ms: int = 0
    collect_ms: int = 0
    total_attempt_ms: int = 0


@dataclass(frozen=True)
class NativeHostCapabilities:
    host_id: str
    available: bool
    max_concurrency: int = 1
    supports_cancel: bool = False
    supports_questions: bool = False
    supports_usage: bool = False
    reason: str = ""


class NativeHostPort(Protocol):
    """Host-provided subagent/session seam; provider adapters arrive in PR5."""

    host_id: str

    def probe(self) -> NativeHostCapabilities: ...
    async def spawn_subagent(self, *, attempt_id: str, context: ContextBundle) -> str: ...
    async def send_prompt(self, runtime_id: str, prompt: str) -> None: ...
    async def poll(self, runtime_id: str) -> Mapping[str, Any]: ...
    async def cancel(self, runtime_id: str, reason: str) -> None: ...
    async def collect(self, runtime_id: str) -> ExecutionResult: ...


class ExecutionAdapter(Protocol):
    adapter_id: str

    def probe(self) -> AdapterCapabilities: ...
    async def prepare_run(self, plan: RunPlan) -> RuntimeRunHandle: ...
    async def start_session(self, node: NodeSpec) -> SessionHandle: ...
    async def dispatch(self, session: SessionHandle, node: NodeSpec,
                       context: ContextBundle) -> DispatchHandle: ...
    def events(self, dispatch: DispatchHandle) -> AsyncIterator[RuntimeEvent]: ...
    async def acknowledge(self, event: RuntimeEvent) -> None: ...
    async def cancel(self, dispatch: DispatchHandle, reason: str) -> None: ...
    async def collect(self, dispatch: DispatchHandle) -> ExecutionResult: ...
    async def release(self, session: SessionHandle) -> None: ...
