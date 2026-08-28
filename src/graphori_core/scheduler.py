"""Pure scheduling decisions for a committed Graphori v2 plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .run_plan import NodeSpec, RunPlan


_ACTIVE = frozenset({"assigned", "dispatched", "running", "stale", "outcome_unknown"})
_AWAITING_VERIFICATION = "awaiting_verification"
_SUCCESS = frozenset({"passed", "complete", "completed", "succeeded"})
_FAILURE = frozenset({"failed", "cancelled", "blocked", "rejected", "inconclusive"})


@dataclass(frozen=True)
class SchedulerPolicy:
    max_wip: int = 2
    min_parallel_gain_ms: int = 30_000
    min_parallel_gain_ratio: float = 0.15
    duplicated_context_ms: int = 0
    handoff_ms: int = 0
    fan_in_ms: int = 0
    extra_verification_ms: int = 0

    def __post_init__(self) -> None:
        if self.max_wip < 1:
            raise ValueError("max_wip must be at least 1")


@dataclass(frozen=True)
class SchedulingState:
    node_states: Mapping[str, str] = field(default_factory=dict)
    approved_nodes: frozenset[str] = frozenset()
    queue_age_ms: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchDecision:
    node_id: str
    reason: str


@dataclass(frozen=True)
class SchedulingBatch:
    dispatches: tuple[DispatchDecision, ...] = ()
    ready: tuple[str, ...] = ()
    waiting: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    estimated_parallel_gain_ms: int = 0


def _overlap(left: str, right: str) -> bool:
    a, b = left.rstrip("/"), right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _scope_conflict(left: NodeSpec, right: NodeSpec) -> bool:
    if any(_overlap(a, b) for a in left.write_scope for b in right.write_scope):
        return True
    if any(_overlap(a, b) for a in left.write_scope for b in right.read_scope):
        return True
    return any(_overlap(a, b) for a in left.read_scope for b in right.write_scope)


class Scheduler:
    """Choose the next bounded, conflict-free dispatch wave.

    The interface accepts only an immutable plan plus a projected state and
    returns a decision batch.  It starts no process and mutates no journal, so
    replaying the same inputs always returns the same answer.
    """

    def __init__(self, policy: SchedulerPolicy = SchedulerPolicy()):
        self.policy = policy

    def _priority(self, plan: RunPlan, state: SchedulingState, node: NodeSpec) -> tuple:
        critical = (plan.critical_path.index(node.node_id)
                    if node.node_id in plan.critical_path else len(plan.nodes) + 1)
        unlocks = sum(node.node_id in candidate.dependencies for candidate in plan.nodes)
        return (critical, -int(state.queue_age_ms.get(node.node_id, 0)),
                -unlocks, bool(node.write_scope), node.node_id)

    def _parallel_gain(self, nodes: tuple[NodeSpec, ...]) -> int:
        if len(nodes) < 2:
            return 0
        sequential = sum(node.estimated_execution_ms for node in nodes)
        parallel = max(node.estimated_execution_ms for node in nodes)
        parallel += sum(node.estimated_startup_ms for node in nodes)
        parallel += (self.policy.duplicated_context_ms + self.policy.handoff_ms
                     + self.policy.fan_in_ms + self.policy.extra_verification_ms)
        return sequential - parallel

    def _profitable(self, nodes: tuple[NodeSpec, ...]) -> bool:
        sequential = sum(node.estimated_execution_ms for node in nodes)
        if sequential <= 0:
            return False
        threshold = max(self.policy.min_parallel_gain_ms,
                        int(sequential * self.policy.min_parallel_gain_ratio))
        return self._parallel_gain(nodes) >= threshold

    def decide(self, plan: RunPlan, state: SchedulingState) -> SchedulingBatch:
        known = {node.node_id: node for node in plan.nodes}
        unknown_state = set(state.node_states) - set(known)
        if unknown_state:
            raise ValueError(f"state references unknown nodes: {sorted(unknown_state)}")

        active = tuple(node for node in plan.nodes
                       if state.node_states.get(node.node_id, "pending") in _ACTIVE)
        waiting: list[str] = []
        blocked: list[str] = []
        candidates: list[NodeSpec] = []
        for node in plan.nodes:
            current = state.node_states.get(node.node_id, "pending")
            if (current in _ACTIVE or current == _AWAITING_VERIFICATION
                    or current in _SUCCESS or current in _FAILURE):
                continue
            dependency_states = [state.node_states.get(dep, "pending")
                                 for dep in node.dependencies]
            if any(item in _FAILURE for item in dependency_states):
                blocked.append(node.node_id)
            elif not all(
                item in _SUCCESS
                or ((node.kind == "verifier" or node.reviews_unverified_dependencies)
                    and item == _AWAITING_VERIFICATION)
                for item in dependency_states
            ):
                waiting.append(node.node_id)
            elif node.approval_required and node.node_id not in state.approved_nodes:
                blocked.append(node.node_id)
            else:
                candidates.append(node)

        candidates.sort(key=lambda item: self._priority(plan, state, item))
        slots = max(0, self.policy.max_wip - len(active))
        selected: list[NodeSpec] = []
        queued: list[str] = []
        for candidate in candidates:
            if len(selected) >= slots:
                queued.append(candidate.node_id)
                continue
            if any(_scope_conflict(candidate, other) for other in (*active, *selected)):
                queued.append(candidate.node_id)
                continue
            if selected and not self._profitable(tuple((*selected, candidate))):
                queued.append(candidate.node_id)
                continue
            selected.append(candidate)

        dispatches = tuple(DispatchDecision(
            item.node_id, "critical_path" if item.node_id in plan.critical_path
            else "parallel_net_gain" if len(selected) > 1 else "ready",
        ) for item in selected)
        return SchedulingBatch(
            dispatches=dispatches,
            ready=tuple(item.node_id for item in candidates),
            waiting=tuple(sorted(waiting)),
            blocked=tuple(sorted(blocked)),
            queued=tuple(queued),
            estimated_parallel_gain_ms=self._parallel_gain(tuple(selected)),
        )
