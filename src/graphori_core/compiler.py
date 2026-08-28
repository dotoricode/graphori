"""Deterministic risk compilation, graph validation, topology, and guards."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .models import (
    Attempt, AttemptState, Edge, EdgeKind, Graph, Gate, Node, NodeKind, Risk,
    Role, Task, TaskMode, TaskState, NodeState, VerificationKind,
)


class GraphValidationError(ValueError):
    pass


class IndependenceError(ValueError):
    pass


class StateTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class RiskInput:
    risk_level: int = 0
    uncertainty: int = 0
    scope: int = 0
    synthesis: int = 0
    parallelism: int = 0
    tags: tuple[str, ...] = ()
    # Missing usage is unknown by contract, never known and never zero.
    usage_status: str = "unknown"
    budget_ok: bool = True
    external_effect: bool | None = None
    # These are deliberately tri-state.  Missing/invalid metadata is unknown,
    # and unknown can never qualify for Fast.
    local_only: bool | None = None
    reversible: bool | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RiskInput":
        def optional_bool(name: str) -> bool | None:
            raw = value.get(name)
            return raw if isinstance(raw, bool) else None

        return cls(
            risk_level=int(value.get("risk_level", 0)),
            uncertainty=int(value.get("uncertainty", 0)),
            scope=int(value.get("scope", 0)),
            synthesis=int(value.get("synthesis", 0)),
            parallelism=int(value.get("parallelism", 0)),
            tags=tuple(str(x) for x in value.get("tags", value.get("risk_tags", ()))),
            usage_status=str(value.get("usage_status", "unknown")),
            budget_ok=value.get("budget_ok") if isinstance(value.get("budget_ok"), bool) else True,
            external_effect=optional_bool("external_effect")
                if "external_effect" in value else optional_bool("external_side_effect"),
            local_only=optional_bool("local_only"),
            reversible=optional_bool("reversible"),
        )


@dataclass(frozen=True)
class RiskResult:
    risk: Risk
    mode: TaskMode
    score: int
    hard_triggers: tuple[str, ...] = ()
    routing_scores: Mapping[str, int] = field(default_factory=dict)


def _risk_input(value: RiskInput | Task | Mapping[str, Any]) -> RiskInput:
    if isinstance(value, RiskInput):
        return value
    if isinstance(value, Task):
        metadata = dict(value.metadata)
        return RiskInput(
            risk_level=value.risk.level,
            uncertainty=int(metadata.get("uncertainty", 0)),
            scope=int(metadata.get("scope", 0)),
            synthesis=int(metadata.get("synthesis", 0)),
            parallelism=int(metadata.get("parallelism", 0)),
            tags=tuple(value.risk_tags),
            usage_status=str(metadata.get("usage_status", "unknown")),
            budget_ok=metadata.get("budget_ok") if isinstance(metadata.get("budget_ok"), bool) else True,
            external_effect=(metadata.get("external_effect")
                             if isinstance(metadata.get("external_effect"), bool)
                             else metadata.get("external_side_effect")
                             if isinstance(metadata.get("external_side_effect"), bool)
                             else None),
            local_only=metadata.get("local_only") if isinstance(metadata.get("local_only"), bool) else None,
            reversible=metadata.get("reversible") if isinstance(metadata.get("reversible"), bool) else None,
        )
    return RiskInput.from_mapping(value)


def compile_risk(value: RiskInput | Task | Mapping[str, Any] | None = None, **overrides: Any) -> RiskResult:
    """Compile risk without ever downgrading a Critical task.

    Unknown usage is a Standard investigation trigger by itself. Fast is
    eligible only with known usage, low risk, no uncertainty, and no external
    effect; budget failures and high-risk tags are Critical hard triggers.
    """
    raw = _risk_input(value) if value is not None else RiskInput()
    if overrides:
        raw = RiskInput.from_mapping({**raw.__dict__, **overrides})
    tags = {tag.lower().replace("_", "-") for tag in raw.tags}
    hard_names = {
        "security-boundary", "security", "reproducibility", "personal-data",
        "external-side-effect", "external-effect", "adversarial", "critical",
        "high-risk", "high-risk-tag", "destructive",
    }
    triggers: list[str] = []
    if raw.risk_level >= 3:
        triggers.append("risk_level")
    if raw.uncertainty >= 2:
        triggers.append("uncertainty")
    if tags & hard_names:
        triggers.append("hard_tag")
    if raw.external_effect is True:
        triggers.append("external_side_effect")
    if not raw.budget_ok:
        triggers.append("budget")
    usage_status = str(raw.usage_status).strip().lower()
    if usage_status not in {"known", "estimate", "unknown"}:
        usage_status = "unknown"
    usage_unknown = usage_status == "unknown"
    score = (3 * max(0, raw.risk_level) + 2 * max(0, raw.uncertainty)
             + 2 * max(0, raw.scope) + 2 * max(0, raw.synthesis)
             + max(0, raw.parallelism))
    if triggers:
        risk, mode = Risk.CRITICAL, TaskMode.CRITICAL
    elif (usage_unknown or usage_status != "known" or raw.uncertainty > 0
          or raw.local_only is not True or raw.reversible is not True
          or raw.external_effect is not False):
        if score >= 7 or raw.risk_level >= 2:
            risk = Risk.HIGH
        elif score >= 3 or raw.risk_level >= 1:
            risk = Risk.MEDIUM
        else:
            risk = Risk.LOW
        mode = TaskMode.STANDARD
    elif score >= 7 or raw.risk_level >= 2:
        risk, mode = Risk.HIGH, TaskMode.STANDARD
    elif score >= 3 or raw.risk_level >= 1:
        risk, mode = Risk.MEDIUM, TaskMode.STANDARD
    else:
        risk, mode = Risk.LOW, TaskMode.FAST
    if usage_unknown:
        triggers.append("usage_unknown")
    routing = {
        "risk": max(0, raw.risk_level), "uncertainty": max(0, raw.uncertainty),
        "scope": max(0, raw.scope), "synthesis": max(0, raw.synthesis),
        "parallelism": max(0, raw.parallelism),
    }
    return RiskResult(risk, mode, score, tuple(sorted(set(triggers))), routing)


def validate_graph(graph: Graph) -> None:
    """Validate references, history invariants, verification paths, and DAG edges."""
    for edge in graph.edges:
        if edge.source not in graph.nodes or edge.target not in graph.nodes:
            raise GraphValidationError(f"unknown edge endpoint: {edge}")
        if edge.source == edge.target:
            raise GraphValidationError(f"self-loop: {edge.source}")
        if edge.kind is EdgeKind.REWORK_OF and edge.target not in graph.nodes:
            raise GraphValidationError(f"history edge has missing target: {edge}")

    # History is not scheduling, but it is still a directed graph.  Check it
    # independently so a 2/3-node (or longer) rework loop cannot hide behind
    # the scheduling-DAG exception below.
    history_adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.kind is EdgeKind.REWORK_OF:
            history_adjacency[edge.source].append(edge.target)
    history_visiting: set[str] = set()
    history_visited: set[str] = set()

    def visit_history(node_id: str) -> None:
        if node_id in history_visiting:
            raise GraphValidationError("rework_of history contains a cycle")
        if node_id in history_visited:
            return
        history_visiting.add(node_id)
        for target in history_adjacency[node_id]:
            visit_history(target)
        history_visiting.remove(node_id)
        history_visited.add(node_id)

    for node_id in graph.nodes:
        visit_history(node_id)

    # A verifier relationship is explicit and cannot be represented by a
    # role-looking string or an arbitrary scheduling edge.
    for node in graph.nodes.values():
        if node.kind is not NodeKind.VERIFIER:
            continue
        related = [edge for edge in graph.edges
                   if edge.kind is EdgeKind.VERIFIES and edge.source == node.node_id]
        if node.metadata.get("fan_in"):
            if not any(graph.nodes[edge.target].kind is NodeKind.VERIFIER for edge in related):
                raise GraphValidationError(f"fan-in verifier has no verification path: {node.node_id}")
        elif not any(graph.nodes[edge.target].kind is NodeKind.WORKER for edge in related):
            raise GraphValidationError(f"verifier has no worker verification path: {node.node_id}")
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.kind in (EdgeKind.REQUIRES, EdgeKind.REQUIRES_GATE):
            adjacency[edge.source].append(edge.target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise GraphValidationError("scheduling graph contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in adjacency[node_id]:
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph.nodes:
        visit(node_id)


@dataclass
class CompiledTopology:
    task: Task
    graph: Graph
    result: RiskResult
    roles: dict[str, Role] = field(default_factory=dict)

    def node_ids(self, kind: NodeKind) -> list[str]:
        return [node.node_id for node in self.graph.nodes.values() if node.kind is kind]


def _node(graph: Graph, node_id: str, kind: NodeKind, label: str,
          role: Role | None = None, **metadata: Any) -> None:
    graph.add_node(Node(node_id, kind, label, role=role, metadata=metadata))


def _edge(graph: Graph, source: str, target: str,
          kind: EdgeKind = EdgeKind.REQUIRES) -> None:
    graph.add_edge(Edge(source, target, kind))


def _independence_key(role: Role) -> tuple[str, str, str, str, str, str]:
    return role.identity, role.provider, role.model, role.checkout, role.session, role.worktree


def _independent(first: Role, second: Role, *, context: str = "") -> bool:
    """Single source of truth for all execution-role independence checks."""
    if first.identity == second.identity:
        return False
    # A shared non-empty execution resource is never independent; an empty
    # value means the resource was not assigned and is handled by the
    # provider/model/checkout context checks below.
    if first.checkout and first.checkout == second.checkout:
        return False
    if first.session and first.session == second.session:
        return False
    if first.worktree and first.worktree == second.worktree:
        return False
    if context in {"critical_verifier", "human_gate"}:
        if (first.provider, first.model) == (second.provider, second.model):
            return False
    if context == "standard_worker_verifier":
        if (first.provider, first.model, first.checkout) == (second.provider, second.model, second.checkout):
            return False
    return True


def _assert_verifier_independent(worker: Role, verifier: Role) -> None:
    if verifier.role is not NodeKind.VERIFIER:
        raise IndependenceError("verifier assignment must use verifier role")
    if not _independent(worker, verifier, context="standard_worker_verifier"):
        raise IndependenceError("verifier must be independent from worker")


def _default_gate_pool() -> tuple[Role, Role]:
    return (
        Role("role_human_gate_0", NodeKind.HUMAN_GATE, "human-gate-0", "gate-provider-a", "gate-model-a", "gate-checkout-a", router_role="human_gate"),
        Role("role_human_gate_1", NodeKind.HUMAN_GATE, "human-gate-1", "gate-provider-b", "gate-model-b", "gate-checkout-b", router_role="human_gate"),
    )


def _review_triggered(task: Task) -> bool:
    return any(bool(task.metadata.get(name)) for name in (
        "verification_required", "independent_verification", "milestone",
        "public_api", "irreversible", "high_uncertainty", "human_gate",
    ))


def _requires_verifier(task: Task, mode: TaskMode) -> bool:
    """Return whether this task needs a separate verifier actor.

    Fast work uses deterministic checks in the owning session.  Standard work
    only pays the startup and handoff cost for an independent verifier when a
    review trigger is explicit.  Critical work always requires one verifier,
    but parallel verifier branches remain opt-in.
    """
    if mode is TaskMode.CRITICAL:
        return True
    if mode is TaskMode.FAST:
        return False
    return _review_triggered(task)


def compile_topology(task: Task, *, mode: TaskMode | None = None,
                     verifier_roles: tuple[Role, ...] = (),
                     human_gate_roles: tuple[Role, ...] = ()) -> CompiledTopology:
    result = compile_risk(task)
    selected = mode or task.mode or result.mode
    # Explicit mode can add review depth, but can never downgrade compiled risk.
    if selected is TaskMode.FAST and result.mode is not TaskMode.FAST:
        selected = result.mode
    if result.mode is TaskMode.CRITICAL:
        selected = TaskMode.CRITICAL
    if selected is TaskMode.FAST and _review_triggered(task):
        selected = TaskMode.STANDARD
    task.mode, task.risk = selected, result.risk
    graph = Graph()
    worker_role = Role("role_worker", NodeKind.WORKER, "worker",
                       str(task.metadata.get("worker_provider", "")),
                       str(task.metadata.get("worker_model", "")),
                       str(task.metadata.get("worker_checkout", "")),
                       str(task.metadata.get("worker_session", "")),
                       str(task.metadata.get("worker_worktree", "")),
                       "worker")
    router_role = Role("role_router", NodeKind.ROUTER, "router", "router-provider",
                       "router-model", "router-checkout", "router-session", "router-worktree", "router")
    _node(graph, "router", NodeKind.ROUTER, "Router", router_role)
    _node(graph, "worker", NodeKind.WORKER, "Worker", worker_role)
    _edge(graph, "router", "worker")
    roles: dict[str, Role] = {"router": router_role, "worker": worker_role}
    if selected is TaskMode.STANDARD and _requires_verifier(task, selected):
        verifier = verifier_roles[0] if verifier_roles else Role(
            "role_verifier_targeted", NodeKind.VERIFIER, "targeted-verifier", "target-provider", "target-model", "target-checkout")
        _assert_verifier_independent(worker_role, verifier)
        _node(graph, "verifier", NodeKind.VERIFIER, "Targeted Verifier", verifier,
              verification=VerificationKind.TARGETED.value)
        _edge(graph, "worker", "verifier")
        _edge(graph, "verifier", "worker", EdgeKind.VERIFIES)
        roles["verifier"] = verifier
        if bool(task.metadata.get("human_gate", False)):
            gate_pool = human_gate_roles or _default_gate_pool()
            _validate_gate_pool(gate_pool, worker_role, (verifier,), router_role)
            gate_role = gate_pool[0]
            _node(graph, "human_gate", NodeKind.HUMAN_GATE, "Human Gate", gate_role,
                  authority_pool=len(gate_pool))
            _edge(graph, "verifier", "human_gate", EdgeKind.REQUIRES_GATE)
            roles.update({"human_gate": gate_role, "human_gate_0": gate_pool[0]})
    elif selected is TaskMode.CRITICAL and bool(task.metadata.get("parallel_verification", False)):
        normal = verifier_roles[0] if len(verifier_roles) > 0 else Role(
            "role_verifier_normal", NodeKind.VERIFIER, "normal-verifier", "provider-a", "model-a", "checkout-a")
        adversarial = verifier_roles[1] if len(verifier_roles) > 1 else Role(
            "role_verifier_adversarial", NodeKind.VERIFIER, "adversarial-verifier", "provider-b", "model-b", "checkout-b")
        _assert_verifier_independent(worker_role, normal)
        _assert_verifier_independent(worker_role, adversarial)
        if not independent_verifier(normal, adversarial):
            raise IndependenceError("Critical verifier roles must be independent")
        _node(graph, "verifier_normal", NodeKind.VERIFIER, "Normal Verifier", normal,
              verification=VerificationKind.FRESH_FULL.value, branch="normal")
        _node(graph, "verifier_adversarial", NodeKind.VERIFIER, "Adversarial Verifier", adversarial,
              verification=VerificationKind.ADVERSARIAL.value, branch="adversarial")
        _edge(graph, "worker", "verifier_normal")
        _edge(graph, "worker", "verifier_adversarial")
        _edge(graph, "verifier_normal", "worker", EdgeKind.VERIFIES)
        _edge(graph, "verifier_adversarial", "worker", EdgeKind.VERIFIES)
        _node(graph, "verifier_fanin", NodeKind.VERIFIER, "Fan-in Verifier", fan_in=True)
        _edge(graph, "verifier_normal", "verifier_fanin")
        _edge(graph, "verifier_adversarial", "verifier_fanin")
        _edge(graph, "verifier_fanin", "verifier_normal", EdgeKind.VERIFIES)
        _edge(graph, "verifier_fanin", "verifier_adversarial", EdgeKind.VERIFIES)
        gate_pool = human_gate_roles or _default_gate_pool()
        _validate_gate_pool(gate_pool, worker_role, (normal, adversarial), router_role)
        gate_role = gate_pool[0]
        _node(graph, "human_gate", NodeKind.HUMAN_GATE, "Human Gate", gate_role,
              authority_pool=len(gate_pool), gate_role="human_gate")
        _edge(graph, "verifier_fanin", "human_gate", EdgeKind.REQUIRES_GATE)
        roles.update({"verifier_normal": normal, "verifier_adversarial": adversarial,
                      "human_gate": gate_role, "human_gate_0": gate_pool[0],
                      "human_gate_1": gate_pool[1]})
    elif selected is TaskMode.CRITICAL:
        verifier = verifier_roles[0] if verifier_roles else Role(
            "role_verifier_critical", NodeKind.VERIFIER, "critical-verifier",
            "critical-provider", "critical-model", "critical-checkout")
        _assert_verifier_independent(worker_role, verifier)
        _node(graph, "verifier", NodeKind.VERIFIER, "Critical Verifier", verifier,
              verification=VerificationKind.FRESH_FULL.value)
        _edge(graph, "worker", "verifier")
        _edge(graph, "verifier", "worker", EdgeKind.VERIFIES)
        gate_pool = human_gate_roles or _default_gate_pool()
        _validate_gate_pool(gate_pool, worker_role, (verifier,), router_role)
        gate_role = gate_pool[0]
        _node(graph, "human_gate", NodeKind.HUMAN_GATE, "Human Gate", gate_role,
              authority_pool=len(gate_pool), gate_role="human_gate")
        _edge(graph, "verifier", "human_gate", EdgeKind.REQUIRES_GATE)
        roles.update({"verifier": verifier, "human_gate": gate_role,
                      "human_gate_0": gate_pool[0], "human_gate_1": gate_pool[1]})
    _node(graph, "observer", NodeKind.OBSERVER, "Observer")
    terminal = ("human_gate" if "human_gate" in graph.nodes else
                "verifier" if "verifier" in graph.nodes else "worker")
    _edge(graph, terminal, "observer", EdgeKind.OBSERVES)
    validate_graph(graph)
    return CompiledTopology(task, graph, result, roles)


def _validate_gate_pool(pool: tuple[Role, ...], worker: Role,
                        verifiers: tuple[Role, ...], router: Role | None = None) -> None:
    if len(pool) < 2:
        raise IndependenceError("Human Gate authority pool must contain at least two roles")
    if any(role.role is not NodeKind.HUMAN_GATE for role in pool):
        raise IndependenceError("authority pool must use human_gate roles")
    for index, role in enumerate(pool):
        for other in pool[index + 1:]:
            if not _independent(role, other, context="human_gate"):
                raise IndependenceError("Human Gate authority roles must be independent")
        for execution in (worker, *verifiers):
            if not _independent(role, execution, context="human_gate"):
                raise IndependenceError("Human Gate authority must be independent from execution roles")
        if router is not None and not _independent(role, router, context="human_gate"):
            raise IndependenceError("Human Gate authority must be independent from Router")
        if (router is not None and role.router_role and router.router_role
                and role.router_role == router.router_role):
            raise IndependenceError("Router and Human Gate router_role values must differ")
        if role.router_role and role.router_role == "router":
            raise IndependenceError("Human Gate role cannot masquerade as Router")


def independent_verifier(first: Role | Attempt, second: Role | Attempt) -> bool:
    a = first.actor if isinstance(first, Attempt) else first
    b = second.actor if isinstance(second, Attempt) else second
    if a.role is not NodeKind.VERIFIER or b.role is not NodeKind.VERIFIER:
        return False
    return _independent(a, b, context="critical_verifier")


def verify_attempt(builder_attempt: Attempt, verifier_attempt: Attempt) -> None:
    if builder_attempt.attempt_id == verifier_attempt.attempt_id:
        raise IndependenceError("a verifier cannot verify the same attempt")
    if builder_attempt.task_id != verifier_attempt.task_id:
        raise IndependenceError("attempts belong to different tasks")
    if verifier_attempt.actor.role is not NodeKind.VERIFIER:
        raise IndependenceError("verification attempt must have verifier role")
    if not _independent(builder_attempt.actor, verifier_attempt.actor,
                        context="standard_worker_verifier"):
        raise IndependenceError("verifier is not independent from builder")


class RevisionAction(str, Enum):
    REVISED = "revised"
    ESCALATED = "human_gate_required"
    IGNORED = "ignored"


@dataclass
class RevisionController:
    # Active MVP policy (ADR 0005): allow one automatic fix, then require a
    # Human Gate.  Callers may still pass an explicit limit for a deliberately
    # different policy (for example, a historical fixture), but the default
    # used by Graphori is intentionally fail-closed at one revision.
    max_revisions: int = 1
    revise_count: int = 0
    revisions: list[str] = field(default_factory=list)
    gate: Gate | None = None

    def record(self, verdict: str, task: Task | None = None,
               graph: Graph | None = None) -> RevisionAction:
        if str(verdict).lower() != "revise":
            return RevisionAction.IGNORED
        if self.revise_count >= self.max_revisions:
            if task is not None and graph is not None:
                latest_node = (task.task_id if self.revise_count == 0
                               else f"{task.task_id}:revision-{self.revise_count}")
                if latest_node not in graph.nodes:
                    raise GraphValidationError(
                        f"revision history is missing current node: {latest_node}"
                    )
            if task is not None:
                task.state = TaskState.ESCALATED
            if graph is not None:
                gate_id = f"human_gate:revision:{self.revise_count + 1}"
                if gate_id not in graph.nodes:
                    graph.add_node(Node(gate_id, NodeKind.HUMAN_GATE, "Human Gate",
                                        metadata={"signal": "human_gate_required", "reason": "revise_limit"}))
                if task is not None:
                    latest_node = task.task_id if self.revise_count == 0 else f"{task.task_id}:revision-{self.revise_count}"
                    _edge(graph, latest_node, gate_id, EdgeKind.REQUIRES_GATE)
            self.gate = Gate(f"gate:revision:{self.revise_count + 1}", "revise_limit")
            return RevisionAction.ESCALATED
        # Capture and validate the current immutable node before changing any
        # controller, task, or graph state.  Missing history must fail
        # explicitly rather than silently producing an un-auditable revision.
        old_node = None
        if task is not None:
            old_node = (task.task_id if self.revise_count == 0
                        else f"{task.task_id}:revision-{self.revise_count}")
            if graph is not None and old_node not in graph.nodes:
                raise GraphValidationError(f"revision history is missing current node: {old_node}")
        if task is not None and graph is not None:
            candidate_id = f"{task.task_id}:revision-{self.revise_count + 1}"
            if candidate_id in graph.nodes:
                raise GraphValidationError(f"revision node already exists: {candidate_id}")
        self.revise_count += 1
        if task is not None:
            task.revision_id = f"revision-{self.revise_count}"
            # The logical task now points at the new immutable revision node.
            task.state = TaskState.READY
            self.revisions.append(task.revision_id)
            if graph is not None:
                new_id = f"{task.task_id}:{task.revision_id}"
                graph.add_node(Node(new_id, NodeKind.WORKER, f"Revision {self.revise_count}",
                                    metadata={"revision_id": task.revision_id}))
                _edge(graph, new_id, old_node, EdgeKind.REWORK_OF)
        return RevisionAction.REVISED


TASK_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.PLANNED: frozenset({TaskState.READY, TaskState.BLOCKED}),
    TaskState.READY: frozenset({TaskState.RUNNING, TaskState.BLOCKED}),
    TaskState.RUNNING: frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.BLOCKED, TaskState.ESCALATED}),
    # Failed nodes are immutable; rework is represented by a new revision node.
    TaskState.FAILED: frozenset({TaskState.ESCALATED}),
    TaskState.BLOCKED: frozenset({TaskState.READY, TaskState.ESCALATED}),
    TaskState.SUCCEEDED: frozenset(),
    TaskState.ESCALATED: frozenset({TaskState.BLOCKED, TaskState.READY}),
}


# Canonical NodeState transition table.  Terminal outcomes are immutable;
# rework creates a new revision node instead of reviving this node.
NODE_TRANSITIONS: dict[NodeState, frozenset[NodeState]] = {
    NodeState.PENDING: frozenset({NodeState.READY, NodeState.BLOCKED}),
    NodeState.READY: frozenset({NodeState.ASSIGNED, NodeState.CANCELLED,
                                NodeState.BLOCKED}),
    NodeState.ASSIGNED: frozenset({NodeState.RUNNING, NodeState.CANCELLED,
                                   NodeState.OUTCOME_UNKNOWN, NodeState.BLOCKED}),
    NodeState.RUNNING: frozenset({NodeState.AWAITING_VERIFICATION, NodeState.FAILED,
                                  NodeState.CANCELLED, NodeState.STALE,
                                  NodeState.OUTCOME_UNKNOWN, NodeState.BLOCKED}),
    NodeState.AWAITING_VERIFICATION: frozenset({NodeState.PASSED, NodeState.FAILED,
                                                NodeState.INCONCLUSIVE, NodeState.BLOCKED}),
    NodeState.QUEUED: frozenset({NodeState.ASSIGNED, NodeState.BLOCKED}),
    NodeState.STALE: frozenset({NodeState.OUTCOME_UNKNOWN, NodeState.BLOCKED}),
    NodeState.OUTCOME_UNKNOWN: frozenset({NodeState.READY, NodeState.CANCELLED,
                                          NodeState.BLOCKED}),
    NodeState.BLOCKED: frozenset({NodeState.READY, NodeState.CANCELLED}),
    NodeState.PASSED: frozenset(),
    NodeState.FAILED: frozenset(),
    NodeState.CANCELLED: frozenset(),
    NodeState.REJECTED: frozenset(),
    NodeState.INCONCLUSIVE: frozenset(),
}


def transition_node(statuses: dict[str, NodeState], node_id: str,
                    target: NodeState) -> NodeState:
    """Apply the canonical transition to one node, fail-closed."""
    if not isinstance(node_id, str) or not node_id.strip():
        raise StateTransitionError("node_id is required")
    try:
        target = NodeState(target)
    except (TypeError, ValueError) as exc:
        raise StateTransitionError(f"unknown node state: {target!r}") from exc
    current = statuses.get(node_id, NodeState.PENDING)
    if target is current:
        return current
    if target not in NODE_TRANSITIONS[current]:
        raise StateTransitionError(f"invalid node transition {current} -> {target}")
    statuses[node_id] = target
    return target


def transition_task(task: Task, target: TaskState) -> Task:
    try:
        target = TaskState(target)
    except (TypeError, ValueError) as exc:
        raise StateTransitionError(f"unknown task state: {target!r}") from exc
    if target not in TASK_TRANSITIONS[task.state]:
        raise StateTransitionError(f"invalid task transition {task.state} -> {target}")
    task.state = target
    return task


ATTEMPT_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    AttemptState.PLANNED: frozenset({AttemptState.DISPATCHED, AttemptState.CANCELLED}),
    AttemptState.DISPATCHED: frozenset({AttemptState.RUNNING, AttemptState.LOST, AttemptState.CANCELLED}),
    AttemptState.RUNNING: frozenset({AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED, AttemptState.TIMED_OUT, AttemptState.LOST}),
    AttemptState.TIMED_OUT: frozenset({AttemptState.OUTCOME_UNKNOWN}),
    AttemptState.LOST: frozenset({AttemptState.OUTCOME_UNKNOWN}),
    AttemptState.OUTCOME_UNKNOWN: frozenset(),
    AttemptState.SUCCEEDED: frozenset(), AttemptState.FAILED: frozenset(), AttemptState.CANCELLED: frozenset(),
}


def transition_attempt(attempt: Attempt, target: AttemptState) -> Attempt:
    try:
        target = AttemptState(target)
    except (TypeError, ValueError) as exc:
        raise StateTransitionError(f"unknown attempt state: {target!r}") from exc
    if target not in ATTEMPT_TRANSITIONS[attempt.state]:
        raise StateTransitionError(f"invalid attempt transition {attempt.state} -> {target}")
    attempt.state = target
    return attempt
