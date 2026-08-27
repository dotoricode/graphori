"""Canonical Graphori enums and immutable-ish domain records.

The core intentionally contains no runtime, OS, provider, or Orca imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class _ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class TaskMode(_ValueEnum):
    FAST = "fast"
    STANDARD = "standard"
    CRITICAL = "critical"


class Risk(_ValueEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def level(self) -> int:
        return {Risk.LOW: 0, Risk.MEDIUM: 1, Risk.HIGH: 2, Risk.CRITICAL: 3}[self]


class NodeKind(_ValueEnum):
    ROUTER = "router"
    WORKER = "worker"
    VERIFIER = "verifier"
    OBSERVER = "observer"
    HUMAN_GATE = "human_gate"
    PLATFORM_GATE = "platform_gate"


class EdgeKind(_ValueEnum):
    REQUIRES = "requires"
    REQUIRES_GATE = "requires_gate"
    VERIFIES = "verifies"
    OBSERVES = "observes"
    REWORK_OF = "rework_of"


class NodeState(_ValueEnum):
    PENDING = "pending"
    READY = "ready"
    ASSIGNED = "assigned"
    RUNNING = "running"
    AWAITING_VERIFICATION = "awaiting_verification"
    QUEUED = "queued"
    STALE = "stale"
    OUTCOME_UNKNOWN = "outcome_unknown"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class TaskState(_ValueEnum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


class AttemptState(_ValueEnum):
    PLANNED = "planned"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LOST = "lost"
    OUTCOME_UNKNOWN = "outcome_unknown"


class VerdictKind(_ValueEnum):
    PENDING = "pending"
    PASS = "pass"
    REVISE = "revise"
    APPROVE = "approve"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


class LivenessState(_ValueEnum):
    CONNECTED = "connected"
    HEARTBEAT_RECENT = "heartbeat_recent"
    STALE = "stale"
    DEAD = "dead"
    UNKNOWN = "unknown"


class UsageStatus(_ValueEnum):
    KNOWN = "known"
    ESTIMATE = "estimate"
    UNKNOWN = "unknown"


class PlatformStatus(_ValueEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_VERIFIED = "not_verified"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


class VerificationKind(_ValueEnum):
    NONE = "none"
    AUTOMATIC = "automatic"
    TARGETED = "targeted"
    FRESH_FULL = "fresh_full"
    ADVERSARIAL = "adversarial"


class ProgressState(_ValueEnum):
    NONE = "none"
    REPORTED = "reported"
    ADVANCED = "advanced"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class TerminalStatus(_ValueEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"


class RunState(_ValueEnum):
    """Non-terminal lifecycle state for a Run.

    Terminal outcomes belong to :class:`TerminalStatus`, the canonical event
    protocol enum.  Keeping lifecycle and terminal state separate avoids two
    enums disagreeing about the meaning of a finished run.
    """

    PLANNED = "planned"
    RUNNING = "running"


@dataclass(frozen=True)
class Role:
    role_id: str
    role: NodeKind
    identity: str
    provider: str = ""
    model: str = ""
    checkout: str = ""
    session: str = ""
    worktree: str = ""
    # Explicit canonical context used when comparing Router/Human Gate roles.
    router_role: str = ""


@dataclass(frozen=True)
class Usage:
    status: UsageStatus
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    source: str | None = None
    predicted_tokens: int | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.status is UsageStatus.UNKNOWN:
            return None
        values = [self.input_tokens, self.output_tokens, self.reasoning_tokens]
        if all(value is None for value in values):
            return self.predicted_tokens
        return sum(value or 0 for value in values)

    @property
    def is_known(self) -> bool:
        return self.status is UsageStatus.KNOWN


@dataclass(frozen=True)
class PlatformVerdict:
    platform: str
    status: PlatformStatus
    evidence_id: str | None = None
    confidence: str = "unknown"
    fixture_id: str | None = None
    snapshot_id: str | None = None


@dataclass
class Task:
    task_id: str
    title: str
    risk: Risk = Risk.LOW
    mode: TaskMode | None = None
    state: TaskState = TaskState.PLANNED
    risk_tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    revision_id: str = "revision-0"
    run_id: str | None = None
    graph_version: int = 1


@dataclass
class Attempt:
    attempt_id: str
    task_id: str
    actor: Role
    state: AttemptState = AttemptState.PLANNED
    retry_of: str | None = None
    usage: Usage = field(default_factory=lambda: Usage(UsageStatus.UNKNOWN))


@dataclass(frozen=True)
class Verdict:
    verdict: VerdictKind
    actor: Role
    attempt_id: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Liveness:
    state: LivenessState
    heartbeat_at: float | None = None
    progress: str = "unknown"


@dataclass
class Node:
    node_id: str
    kind: NodeKind
    label: str
    state: NodeState = NodeState.PENDING
    role: Role | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: EdgeKind = EdgeKind.REQUIRES


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(f"edge references missing node: {edge}")
        self.edges.append(edge)


@dataclass
class GraphVersion:
    """A publishable in-memory graph snapshot."""

    version: int = 1
    graph: Graph = field(default_factory=Graph)

    @property
    def graph_version(self) -> int:
        return self.version


@dataclass
class Run:
    """Minimum run identity owned by the portable core."""

    run_id: str
    graph_version: int = 1
    graph: Graph = field(default_factory=Graph)
    # Lifecycle uses RunState until terminal; terminal values use the
    # canonical TerminalStatus enum directly.
    state: RunState | TerminalStatus = RunState.PLANNED
    terminal_status: TerminalStatus | None = None
    task_ids: tuple[str, ...] = ()

    @property
    def is_terminal(self) -> bool:
        return self.terminal_status is not None


@dataclass(frozen=True)
class Gate:
    gate_id: str
    reason: str
    authority_pool: tuple[Role, ...] = ()
    required: bool = True
    signal: str = "human_gate_required"
