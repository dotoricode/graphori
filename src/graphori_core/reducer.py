"""Strict, dependency-free validation and projection of canonical events."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping

from .models import (
    Attempt, AttemptState, Edge, EdgeKind, GraphVersion, Node, NodeKind,
    NodeState, PlatformStatus, PlatformVerdict, Role, Run, RunState, Task,
    TaskState, TerminalStatus,
    VerdictKind,
)
from .compiler import (
    StateTransitionError, transition_attempt, transition_node, transition_task,
)


# This set intentionally mirrors EVENT_PROTOCOL.md.  task_status_changed is
# not canonical and therefore cannot be smuggled into the reducer.
EVENT_TYPES = frozenset({
    "run_created", "graph_published", "node_created", "edge_created", "role_assigned",
    "assignment_rejected", "attempt_dispatched", "heartbeat", "progress_reported",
    "worker_finished", "verdict_recorded", "gate_created", "gate_resolved",
    "platform_verdict_recorded", "usage_recorded", "node_status_changed", "retry_created",
    "rework_created",
    "runtime_binding_recorded", "runtime_resource_changed", "routing_observed",
    "stale_marked", "reconciled", "duplicate_ignored", "idempotency_conflict",
    "event_quarantined", "run_terminal",
})

_REQUIRED_ENVELOPE = (
    "schema_version", "event_id", "producer_event_id", "run_id", "graph_version", "seq",
    "occurred_at", "recorded_at", "actor", "type", "entity", "payload",
    "prev_digest", "digest",
)

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-fA-F]{64}$")

# A completed Run may contain successful or non-successful terminal node
# outcomes.  ``stale`` and ``outcome_unknown`` remain open because the
# protocol requires reconciliation or an explicit retry before completion.
_TERMINAL_NODE_STATES = frozenset({
    NodeState.PASSED, NodeState.FAILED, NodeState.CANCELLED,
    NodeState.BLOCKED, NodeState.REJECTED, NodeState.INCONCLUSIVE,
})

_EXECUTION_NODE_KINDS = frozenset({
    NodeKind.ROUTER, NodeKind.WORKER, NodeKind.VERIFIER,
    NodeKind.HUMAN_GATE, NodeKind.PLATFORM_GATE,
})


def _stable(value: Any) -> str:
    """Render graph metadata deterministically for an external-mutation check."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      default=lambda item: getattr(item, "value", repr(item)))


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateTransitionError(f"{name} must be a non-empty string")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StateTransitionError(f"{name} must be an object")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise StateTransitionError(
            f"{name} must match sha256:<64 hex characters>"
        )
    return value


def validate_event_envelope(event: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the persisted canonical envelope before any projection."""
    _mapping(event, "event")
    missing = [name for name in _REQUIRED_ENVELOPE if name not in event]
    if missing:
        raise StateTransitionError(f"missing canonical envelope fields: {', '.join(missing)}")
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise StateTransitionError("schema_version must be integer 1")
    _nonempty_string(event["event_id"], "event_id")
    _nonempty_string(event["producer_event_id"], "producer_event_id")
    _nonempty_string(event["run_id"], "run_id")
    if type(event["graph_version"]) is not int or event["graph_version"] < 1:
        raise StateTransitionError("graph_version must be a positive integer")
    if type(event["seq"]) is not int or event["seq"] < 0:
        raise StateTransitionError("seq must be a non-negative integer")
    _nonempty_string(event["occurred_at"], "occurred_at")
    _nonempty_string(event["recorded_at"], "recorded_at")
    actor = _mapping(event["actor"], "actor")
    _nonempty_string(actor.get("role"), "actor.role")
    _nonempty_string(actor.get("role_id"), "actor.role_id")
    _nonempty_string(event["type"], "type")
    if event["type"] not in EVENT_TYPES:
        raise StateTransitionError(f"unknown event type: {event['type']}")
    entity = _mapping(event["entity"], "entity")
    _nonempty_string(entity.get("task_id"), "entity.task_id")
    if "run_id" in entity and entity["run_id"] != event["run_id"]:
        raise StateTransitionError("entity.run_id must match envelope run_id")
    if "graph_version" in entity and entity["graph_version"] != event["graph_version"]:
        raise StateTransitionError("entity.graph_version must match envelope graph_version")
    _mapping(event["payload"], "payload")
    # EVENT_PROTOCOL presents both values as canonical sha256 digests.  It
    # does not define a null genesis sentinel, so seq=0 still requires the
    # same digest shape; Stage 3 owns computing the actual chain.
    _digest(event["prev_digest"], "prev_digest")
    _digest(event["digest"], "digest")
    if "usage" in event and event["usage"] is not None:
        _mapping(event["usage"], "usage")
    if "platform" in event and event["platform"] is not None:
        _nonempty_string(event["platform"], "platform")
    return event


def canonical_event(event_type: str, *, event_id: str = "evt_test",
                    run_id: str = "run_test", task_id: str = "task_test",
                    seq: int = 1, actor_role: str = "verifier",
                    entity: Mapping[str, Any] | None = None,
                    payload: Mapping[str, Any] | None = None,
                    graph_version: int = 1,
                    occurred_at: str = "2026-08-09T00:00:00Z",
                    recorded_at: str = "2026-08-09T00:00:01Z",
                    **extra: Any) -> dict[str, Any]:
    """Build a complete event fixture using the documented envelope."""
    result: dict[str, Any] = {
        "schema_version": 1, "event_id": event_id, "producer_event_id": f"producer:test:{seq}",
        "run_id": run_id, "graph_version": graph_version, "seq": seq,
        "occurred_at": occurred_at, "recorded_at": recorded_at,
        "actor": {"role": actor_role, "role_id": f"role_{actor_role}"},
        "type": event_type,
        "entity": {"task_id": task_id, **dict(entity or {})},
        "payload": dict(payload or {}),
        "usage": {"status": "unknown"}, "platform": "windows",
        "prev_digest": "sha256:" + "0" * 64, "digest": "sha256:" + "1" * 64,
    }
    result.update(extra)
    return result


@dataclass
class StateReducer:
    task: Task
    run: Run | None = None
    platform_verdicts: dict[str, PlatformVerdict] = field(default_factory=dict)
    verdicts: list[VerdictKind] = field(default_factory=list)
    node_statuses: dict[str, NodeState] = field(default_factory=dict)
    attempts: dict[str, Attempt] = field(default_factory=dict)
    attempt_nodes: dict[str, str] = field(default_factory=dict)
    retry_counts: dict[str, int] = field(default_factory=dict)
    rework_counts: dict[str, int] = field(default_factory=dict)
    rework_nodes: dict[str, str] = field(default_factory=dict)
    verdict_targets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    open_gates: dict[str, str] = field(default_factory=dict)
    gate_records: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    gate_resolutions: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    approved_nodes: set[str] = field(default_factory=set)
    fallback_nodes: set[str] = field(default_factory=set)
    runtime_bindings: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    resource_dispositions: dict[str, str] = field(default_factory=dict)
    routing_observations: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    graph_projection: GraphVersion | None = None
    # A Run object (or a pre-filled task.run_id) is context, not proof that
    # the run_created event was observed.  Keep that fact as explicit state.
    _run_created_applied: bool = field(default=False, init=False, repr=False)
    _graph_was_published: bool = field(default=False, init=False, repr=False)
    _published_topology: tuple[Any, ...] | None = field(default=None, init=False, repr=False)
    _published_node_states: tuple[Any, ...] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.run is not None:
            if self.task.run_id is not None and self.task.run_id != self.run.run_id:
                raise StateTransitionError("task.run_id must match Run.run_id")
            if self.task.run_id is None:
                self.task.run_id = self.run.run_id
            if self.task.graph_version != self.run.graph_version:
                raise StateTransitionError("task.graph_version must match Run.graph_version")
            self.graph_projection = GraphVersion(self.run.graph_version, self.run.graph)
            # Run.graph is canonical; retain the legacy map as a deterministic
            # index for callers that already consume ``node_statuses``.
            self.node_statuses.update({node_id: node.state
                                       for node_id, node in self.run.graph.nodes.items()})
        elif self.task.run_id is not None:
            # Do not synthesize a projected Run from task context.  Lifecycle
            # projection starts only when run_created is actually applied.
            pass

    @property
    def graph_version(self) -> int | None:
        return self.run.graph_version if self.run is not None else None

    def _validate_context(self, event: Mapping[str, Any]) -> None:
        entity = _mapping(event["entity"], "entity")
        event_run_id = event["run_id"]
        lifecycle_event = event["type"] in {"run_created", "graph_published", "run_terminal"}
        if self.run is not None and event_run_id != self.run.run_id:
            raise StateTransitionError("event.run_id does not match projected Run")
        if self.task.run_id is not None and event_run_id != self.task.run_id:
            raise StateTransitionError("event.run_id does not match Task.run_id")
        if (lifecycle_event or self.run is not None or self.task.run_id is not None) and entity.get("task_id") != self.task.task_id:
            raise StateTransitionError("entity.task_id does not match Task.task_id")
        if self.run is not None and event["type"] != "graph_published":
            if event["graph_version"] != self.run.graph_version:
                raise StateTransitionError("event.graph_version does not match projected graph version")

    def _validate_run_created_context(self, event: Mapping[str, Any]) -> None:
        """Require the first lifecycle event to bind every known identity."""
        if self.task.graph_version != event["graph_version"]:
            raise StateTransitionError("run_created graph version does not match Task.graph_version")
        if self.run is not None and self.run.graph_version != event["graph_version"]:
            raise StateTransitionError("run_created graph version does not match Run.graph_version")

    def _execution_nodes(self, run: Run) -> tuple[Any, ...]:
        """Return graph nodes whose execution must be closed for success.

        Observer nodes describe a relationship and do not represent work that
        must reach a terminal outcome.  Every other canonical node kind is an
        execution target, including router, worker, verifier, and gate nodes.
        Keeping this derived from the graph avoids a second node inventory in
        the reducer.
        """
        # A rework edge points from the new revision to the old one.  The old
        # node remains immutable history, not an additional active target.
        replaced = {edge.target for edge in run.graph.edges
                    if str(edge.kind) == "rework_of"}
        return tuple(node for node in run.graph.nodes.values()
                     if node.kind in _EXECUTION_NODE_KINDS
                     and node.node_id not in replaced)

    def _require_execution_nodes_passed(self, run: Run) -> None:
        execution_nodes = self._execution_nodes(run)
        if not execution_nodes:
            raise StateTransitionError(
                "succeeded run requires at least one active execution node"
            )
        not_passed = [node.node_id for node in execution_nodes
                      if node.state is not NodeState.PASSED]
        if not_passed:
            raise StateTransitionError(
                "succeeded run requires all active execution nodes to be passed: "
                + ", ".join(sorted(not_passed))
            )

    def _topology_snapshot(self, run: Run) -> tuple[Any, ...]:
        nodes = tuple(sorted(
            (node.node_id, str(node.kind), node.label, _stable(node.role),
             _stable(node.metadata))
            for node in run.graph.nodes.values()))
        edges = tuple(sorted(
            (edge.source, edge.target, str(edge.kind))
            for edge in run.graph.edges))
        return nodes, edges

    def _node_state_snapshot(self, run: Run) -> tuple[Any, ...]:
        return tuple(sorted((node.node_id, str(node.state))
                            for node in run.graph.nodes.values()))

    def _record_published_snapshot(self, run: Run) -> None:
        self._published_topology = self._topology_snapshot(run)
        self._published_node_states = self._node_state_snapshot(run)
        self.node_statuses = {node_id: node.state
                              for node_id, node in run.graph.nodes.items()}

    def _assert_published_snapshot(self, run: Run) -> None:
        if self._published_topology is None or self._published_node_states is None:
            raise StateTransitionError("published Run is missing its graph snapshot")
        if self._topology_snapshot(run) != self._published_topology:
            raise StateTransitionError("published graph topology was changed externally")
        if self._node_state_snapshot(run) != self._published_node_states:
            raise StateTransitionError("published graph state was changed externally")
        expected = {node_id: node.state for node_id, node in run.graph.nodes.items()}
        if self.node_statuses != expected:
            raise StateTransitionError("Run.graph is not synchronized with reducer state")

    def _require_published_run(self, event_type: str) -> Run:
        run = self.run
        if run is None or not self._run_created_applied or not self._graph_was_published:
            raise StateTransitionError(f"{event_type} requires run_created and graph_published")
        return run

    def _canonical_node_id(self, event: Mapping[str, Any]) -> str:
        entity = _mapping(event["entity"], "entity")
        entity_id = entity.get("node_id")
        entity_id = _nonempty_string(entity_id, "entity.node_id")
        payload = _mapping(event["payload"], "payload")
        if "node_id" in payload:
            payload_id = _nonempty_string(payload["node_id"], "payload.node_id")
            if payload_id != entity_id:
                raise StateTransitionError("entity.node_id and payload.node_id conflict")
        return entity_id

    def _canonical_attempt_id(self, event: Mapping[str, Any]) -> str:
        entity = _mapping(event["entity"], "entity")
        payload = _mapping(event["payload"], "payload")
        value = entity.get("attempt_id", payload.get("attempt_id"))
        attempt_id = _nonempty_string(value, "attempt_id")
        if ("attempt_id" in entity and "attempt_id" in payload
                and entity["attempt_id"] != payload["attempt_id"]):
            raise StateTransitionError("entity.attempt_id and payload.attempt_id conflict")
        return attempt_id

    def _set_node_state(self, node_id: str, target: NodeState) -> None:
        run = self._require_published_run("node transition")
        node = run.graph.nodes.get(node_id)
        if node is None:
            raise StateTransitionError(f"unknown graph node: {node_id}")
        self.node_statuses[node_id] = node.state
        transition_node(self.node_statuses, node_id, target)
        node.state = self.node_statuses[node_id]
        self._published_node_states = self._node_state_snapshot(run)

    def _require_actor_for_node(self, event: Mapping[str, Any], node_id: str) -> str:
        run = self._require_published_run(event["type"])
        node = run.graph.nodes.get(node_id)
        if node is None:
            raise StateTransitionError(f"event references unknown graph node: {node_id}")
        actor = _mapping(event["actor"], "actor")
        actor_role = _nonempty_string(actor.get("role"), "actor.role")
        expected = "verifier" if node.kind is NodeKind.VERIFIER else "worker"
        if actor_role != expected:
            raise StateTransitionError(
                f"{event['type']} actor must be {expected} for node {node_id}"
            )
        if node.role is not None and actor.get("role_id") != node.role.role_id:
            raise StateTransitionError("actor.role_id does not match assigned node role")
        return actor_role

    def _require_terminal_evidence(self, run: Run, status: TerminalStatus,
                                   payload: Mapping[str, Any]) -> None:
        if status is TerminalStatus.REJECTED:
            reason = payload.get("reason", payload.get("rejection_reason"))
            evidence = payload.get("evidence_ids")
            if not ((isinstance(reason, str) and reason.strip()) or
                    (isinstance(evidence, list) and evidence and
                     all(isinstance(item, str) and item.strip() for item in evidence))):
                raise StateTransitionError("rejected terminal requires reason or evidence_ids")
        elif status is TerminalStatus.BLOCKED:
            reason = payload.get("blocking_reason")
            has_blocked_node = any(node.state is NodeState.BLOCKED
                                   for node in self._execution_nodes(run))
            if not has_blocked_node and not (isinstance(reason, str) and reason.strip()):
                raise StateTransitionError("blocked terminal requires blocked node or blocking_reason")
        elif status is TerminalStatus.INCONCLUSIVE:
            reason = payload.get("inconclusive_reason")
            has_inconclusive_node = any(node.state is NodeState.INCONCLUSIVE
                                        for node in self._execution_nodes(run))
            if not has_inconclusive_node and not (isinstance(reason, str) and reason.strip()):
                raise StateTransitionError(
                    "inconclusive terminal requires inconclusive node or inconclusive_reason"
                )

    def _ensure_run(self, event: Mapping[str, Any]) -> Run:
        if self.run is None:
            self.run = Run(event["run_id"], event["graph_version"])
            self.task.run_id = event["run_id"]
            self.graph_projection = GraphVersion(self.run.graph_version, self.run.graph)
        return self.run

    def apply(self, event: Mapping[str, Any]) -> "StateReducer":
        validate_event_envelope(event)
        event_type = event["type"]
        payload = _mapping(event["payload"], "payload")
        self._validate_context(event)
        # Once a Run is terminal, no later event may mutate any projection.
        # This guard deliberately runs before event dispatch, including for
        # lifecycle duplicates and events that would otherwise be ignored.
        if self.run is not None and self.run.is_terminal:
            raise StateTransitionError("Run is terminal; all later events are rejected")
        if self.run is not None and self._graph_was_published:
            self._assert_published_snapshot(self.run)
        if event_type in {"node_created", "edge_created"}:
            # Topology is compiler-owned and sealed by graph_published.  The
            # reducer never creates nodes or edges from an event.
            raise StateTransitionError("topology mutation events are not supported by I02")
        if event_type == "task_status_changed":  # defensive; not canonical
            raw = payload.get("status", payload.get("state"))
            if raw is None:
                raise StateTransitionError("task status is required")
            transition_task(self.task, TaskState(str(raw)))
        elif event_type == "run_created":
            if self._run_created_applied:
                raise StateTransitionError("run_created cannot be duplicated or reopen a Run")
            self._validate_run_created_context(event)
            run = self._ensure_run(event)
            if run.is_terminal or self._graph_was_published:
                raise StateTransitionError("run_created cannot reopen an existing Run")
            if event["graph_version"] != run.graph_version:
                raise StateTransitionError("run_created graph version mismatch")
            self._run_created_applied = True
        elif event_type == "graph_published":
            run = self.run
            if run is None or not self._run_created_applied:
                raise StateTransitionError("graph_published requires run_created")
            if run.is_terminal:
                raise StateTransitionError("graph_published cannot follow run_terminal")
            if self._graph_was_published:
                raise StateTransitionError("graph_published cannot be duplicated")
            version = event["graph_version"]
            if version < run.graph_version:
                raise StateTransitionError("graph version cannot regress")
            run.graph_version = version
            run.state = RunState.RUNNING
            self.task.graph_version = version
            self.graph_projection = GraphVersion(version, run.graph)
            self._graph_was_published = True
            self._record_published_snapshot(run)
        elif event_type == "run_terminal":
            run = self.run
            if run is None or not self._run_created_applied or not self._graph_was_published:
                raise StateTransitionError("run_terminal requires graph_published")
            raw_status = payload.get("terminal_status")
            try:
                status = TerminalStatus(raw_status)
            except (TypeError, ValueError) as exc:
                raise StateTransitionError(f"invalid terminal_status: {raw_status!r}") from exc
            if run.terminal_status is not None:
                raise StateTransitionError("Run terminal status cannot be changed or duplicated")
            if status is TerminalStatus.SUCCEEDED:
                self._require_execution_nodes_passed(run)
            else:
                self._require_terminal_evidence(run, status, payload)
            run.terminal_status = status
            run.state = status
        elif event_type == "node_status_changed":
            if self.run is not None:
                self._require_published_run(event_type)
            raw = payload.get("status", payload.get("state"))
            if raw is None:
                raise StateTransitionError("node status is required")
            try:
                status = NodeState(str(raw))
            except ValueError as exc:
                raise StateTransitionError(f"invalid node status: {raw!r}") from exc
            actor = _mapping(event["actor"], "actor")
            actor_role = _nonempty_string(actor.get("role"), "actor.role")
            if status is NodeState.PASSED and actor_role not in {"verifier", "human_gate"}:
                raise StateTransitionError(
                    "only verifier or human_gate may mark a node passed"
                )
            node_id = self._canonical_node_id(event)
            if self.run is not None:
                node = self.run.graph.nodes.get(node_id)
                if node is None:
                    raise StateTransitionError(
                        f"node_status_changed references unknown graph node: {node_id}"
                    )
                # Run.graph is the canonical projection.  Seed the reducer's
                # compatibility map from it so an externally prebuilt graph
                # cannot diverge from the map used by transition_node.
                self.node_statuses[node_id] = node.state
            elif node_id not in self.node_statuses:
                # Legacy/task-only callers may transition an explicitly
                # pre-registered inventory entry, but an event can never
                # create a new node or a Run projection implicitly.
                raise StateTransitionError(
                    f"node_status_changed references unknown compatibility node: {node_id}"
                )
            elif not isinstance(self.node_statuses[node_id], NodeState):
                raise StateTransitionError(
                    f"compatibility node has invalid state: {node_id}"
                )
            transition_node(self.node_statuses, node_id, status)
            if self.run is not None:
                self.run.graph.nodes[node_id].state = self.node_statuses[node_id]
                self._published_node_states = self._node_state_snapshot(self.run)
            attempt_id = payload.get("attempt_id")
            if attempt_id is not None:
                attempt_id = _nonempty_string(attempt_id, "payload.attempt_id")
                attempt = self.attempts.get(attempt_id)
                if attempt is None or self.attempt_nodes.get(attempt_id) != node_id:
                    raise StateTransitionError("node transition references unknown attempt")
                if status is NodeState.RUNNING and attempt.state is AttemptState.DISPATCHED:
                    transition_attempt(attempt, AttemptState.RUNNING)
        elif event_type == "attempt_dispatched":
            run = self._require_published_run(event_type)
            actor_role = _nonempty_string(event["actor"].get("role"), "actor.role")
            if actor_role not in {"scheduler", "router"}:
                raise StateTransitionError("only scheduler or router may dispatch attempts")
            node_id = self._canonical_node_id(event)
            node = run.graph.nodes.get(node_id)
            if node is None:
                raise StateTransitionError(f"attempt references unknown node: {node_id}")
            attempt_id = self._canonical_attempt_id(event)
            if attempt_id in self.attempts:
                raise StateTransitionError(f"attempt already exists: {attempt_id}")
            retry_of = payload.get("retry_of")
            if retry_of is not None:
                retry_of = _nonempty_string(retry_of, "payload.retry_of")
                if retry_of not in self.attempts:
                    raise StateTransitionError("retry_of references unknown attempt")
            role = node.role or Role(
                f"role_{node.kind.value}_{node_id}", node.kind,
                f"{node.kind.value}:{node_id}",
            )
            attempt = Attempt(attempt_id, self.task.task_id, role, retry_of=retry_of)
            transition_attempt(attempt, AttemptState.DISPATCHED)
            self.attempts[attempt_id] = attempt
            self.attempt_nodes[attempt_id] = node_id
            self._set_node_state(node_id, NodeState.ASSIGNED)
        elif event_type == "worker_finished":
            self._require_published_run(event_type)
            node_id = self._canonical_node_id(event)
            self._require_actor_for_node(event, node_id)
            attempt_id = self._canonical_attempt_id(event)
            attempt = self.attempts.get(attempt_id)
            if attempt is None or self.attempt_nodes.get(attempt_id) != node_id:
                raise StateTransitionError("worker_finished references unknown attempt")
            if attempt.state is AttemptState.DISPATCHED:
                transition_attempt(attempt, AttemptState.RUNNING)
            raw_outcome = payload.get("outcome")
            outcome = str(raw_outcome if raw_outcome is not None
                          else payload.get("attempt_state", ""))
            # Legacy generic CLI attempts predate retry orchestration. Their
            # explicit process timeout is a completed, failed CLI attempt;
            # the v2 Engine emits ``outcome=timed_out`` and retains unknown
            # semantics so the scheduler can perform its bounded retry.
            if raw_outcome is None and outcome == "outcome_unknown" \
                    and payload.get("timed_out") is True:
                outcome = "failed"
            if outcome == "succeeded":
                transition_attempt(attempt, AttemptState.SUCCEEDED)
                self._set_node_state(node_id, NodeState.AWAITING_VERIFICATION)
            elif outcome in {"timed_out", "timeout"}:
                transition_attempt(attempt, AttemptState.TIMED_OUT)
                transition_attempt(attempt, AttemptState.OUTCOME_UNKNOWN)
                self._set_node_state(node_id, NodeState.OUTCOME_UNKNOWN)
            elif outcome in {
                    "lost", "outcome_unknown", "malformed", "startup_failure",
                    "incomplete_result"}:
                transition_attempt(attempt, AttemptState.LOST)
                transition_attempt(attempt, AttemptState.OUTCOME_UNKNOWN)
                self._set_node_state(node_id, NodeState.OUTCOME_UNKNOWN)
            elif outcome in {"failed", "scope_violation"}:
                transition_attempt(attempt, AttemptState.FAILED)
                self._set_node_state(node_id, NodeState.FAILED)
            elif outcome == "cancelled":
                transition_attempt(attempt, AttemptState.CANCELLED)
                self._set_node_state(node_id, NodeState.CANCELLED)
            else:
                raise StateTransitionError(f"invalid worker outcome: {outcome!r}")
        elif event_type == "reconciled":
            self._require_published_run(event_type)
            node_id = self._canonical_node_id(event)
            attempt_id = self._canonical_attempt_id(event)
            attempt = self.attempts.get(attempt_id)
            if attempt is None or self.attempt_nodes.get(attempt_id) != node_id:
                raise StateTransitionError("reconciled references unknown attempt")
            if attempt.state is AttemptState.DISPATCHED:
                transition_attempt(attempt, AttemptState.LOST)
            elif attempt.state is AttemptState.RUNNING:
                transition_attempt(attempt, AttemptState.LOST)
            else:
                raise StateTransitionError("only in-flight attempts may be reconciled")
            transition_attempt(attempt, AttemptState.OUTCOME_UNKNOWN)
            self._set_node_state(node_id, NodeState.OUTCOME_UNKNOWN)
        elif event_type == "retry_created":
            self._require_published_run(event_type)
            if event["actor"]["role"] != "router":
                raise StateTransitionError("only router may create retry")
            node_id = self._canonical_node_id(event)
            previous = _nonempty_string(payload.get("retry_of"), "payload.retry_of")
            if previous not in self.attempts or self.attempt_nodes[previous] != node_id:
                raise StateTransitionError("retry_of references unknown node attempt")
            count = self.retry_counts.get(node_id, 0) + 1
            if count > 1:
                raise StateTransitionError("automatic retry limit exceeded")
            self.retry_counts[node_id] = count
            self._set_node_state(node_id, NodeState.READY)
        elif event_type == "runtime_binding_recorded":
            self._require_published_run(event_type)
            if event["actor"]["role"] != "router":
                raise StateTransitionError("only router may record runtime bindings")
            node_id = self._canonical_node_id(event)
            attempt_id = self._canonical_attempt_id(event)
            if attempt_id not in self.attempts or self.attempt_nodes[attempt_id] != node_id:
                raise StateTransitionError("runtime binding references unknown attempt")
            required = ("adapter", "external_run_id", "external_task_id", "external_dispatch_id")
            if any(not isinstance(payload.get(name), str) or not payload[name]
                   for name in required):
                raise StateTransitionError("runtime binding requires external identities")
            existing = self.runtime_bindings.get(attempt_id)
            binding = {name: payload[name] for name in required}
            if existing is not None and existing != binding:
                raise StateTransitionError("runtime binding identity conflict")
            self.runtime_bindings[attempt_id] = binding
        elif event_type == "runtime_resource_changed":
            self._require_published_run(event_type)
            if event["actor"]["role"] != "router":
                raise StateTransitionError("only router may record resource disposition")
            self._canonical_node_id(event)
            dispatch_id = _nonempty_string(
                payload.get("external_dispatch_id"), "payload.external_dispatch_id"
            )
            disposition = _nonempty_string(
                payload.get("disposition"), "payload.disposition"
            )
            if disposition not in {
                    "released", "retained_intentionally", "release_pending",
                    "release_failed", "unknown"}:
                raise StateTransitionError("invalid resource disposition")
            self.resource_dispositions[dispatch_id] = disposition
        elif event_type == "routing_observed":
            self._require_published_run(event_type)
            if event["actor"]["role"] != "router":
                raise StateTransitionError("only router may record routing observation")
            node_id = self._canonical_node_id(event)
            attempt_id = self._canonical_attempt_id(event)
            if attempt_id not in self.attempts or self.attempt_nodes[attempt_id] != node_id:
                raise StateTransitionError("routing observation references unknown attempt")
            required = ("requested_model", "requested_effort", "observed_model")
            if any(not isinstance(payload.get(name), str) for name in required):
                raise StateTransitionError("routing observation fields must be strings")
            existing = self.routing_observations.get(attempt_id)
            observation = dict(payload)
            if existing is not None and existing != observation:
                raise StateTransitionError("routing observation conflict")
            self.routing_observations[attempt_id] = observation
        elif event_type == "rework_created":
            run = self._require_published_run(event_type)
            if event["actor"]["role"] not in {"router", "human_gate"}:
                raise StateTransitionError("only router or human_gate may create rework")
            node_id = self._canonical_node_id(event)
            original_id = _nonempty_string(
                payload.get("original_node_id", node_id), "payload.original_node_id"
            )
            if node_id not in run.graph.nodes or original_id not in run.graph.nodes:
                raise StateTransitionError("rework references unknown original node")
            count = self.rework_counts.get(original_id, 0) + 1
            if count > 1:
                raise StateTransitionError("automatic rework limit exceeded")
            rework_node_id = _nonempty_string(
                payload.get("rework_node_id"), "payload.rework_node_id"
            )
            verifier_id = _nonempty_string(
                payload.get("verifier_node_id"), "payload.verifier_node_id"
            )
            rework_verifier_id = _nonempty_string(
                payload.get("rework_verifier_node_id"),
                "payload.rework_verifier_node_id",
            )
            if any(item in run.graph.nodes for item in (rework_node_id, rework_verifier_id)):
                raise StateTransitionError("rework node identity already exists")
            original = run.graph.nodes[node_id]
            verifier = run.graph.nodes.get(verifier_id)
            if verifier is None or verifier.kind is not NodeKind.VERIFIER:
                raise StateTransitionError("rework requires the verifier that requested it")
            worker_role = Role(
                f"role_worker_{rework_node_id}", NodeKind.WORKER,
                f"worker:{rework_node_id}",
            )
            verifier_role = Role(
                f"role_verifier_{rework_verifier_id}", NodeKind.VERIFIER,
                f"verifier:{rework_verifier_id}",
            )
            run.graph.add_node(Node(
                rework_node_id, original.kind, f"{original.label} (rework {count})",
                role=worker_role,
                metadata={"rework_of": node_id, "original_node_id": original_id},
            ))
            run.graph.add_node(Node(
                rework_verifier_id, NodeKind.VERIFIER,
                f"{verifier.label} (rework {count})", role=verifier_role,
                metadata={"rework_of": verifier_id, "original_node_id": verifier_id},
            ))
            run.graph.add_edge(Edge(rework_node_id, node_id, EdgeKind.REWORK_OF))
            run.graph.add_edge(Edge(rework_verifier_id, verifier_id, EdgeKind.REWORK_OF))
            run.graph.add_edge(Edge(rework_verifier_id, rework_node_id, EdgeKind.VERIFIES))
            self.rework_counts[original_id] = count
            self.rework_nodes[original_id] = rework_node_id
            self.node_statuses[rework_node_id] = NodeState.PENDING
            self.node_statuses[rework_verifier_id] = NodeState.PENDING
            self._published_topology = self._topology_snapshot(run)
            self._published_node_states = self._node_state_snapshot(run)
        elif event_type == "gate_created":
            self._require_published_run(event_type)
            if event["actor"]["role"] != "router":
                raise StateTransitionError("only router may create a gate")
            gate_id = _nonempty_string(payload.get("gate_id"), "payload.gate_id")
            reason = _nonempty_string(payload.get("reason"), "payload.reason")
            if gate_id in self.open_gates:
                raise StateTransitionError("gate already exists")
            self.open_gates[gate_id] = reason
            self.gate_records[gate_id] = dict(payload)
        elif event_type == "gate_resolved":
            self._require_published_run(event_type)
            actor_role = event["actor"]["role"]
            decision = _nonempty_string(payload.get("decision"), "payload.decision")
            if decision == "cancelled":
                if actor_role != "router":
                    raise StateTransitionError("only router may cancel a gate with the Run")
            elif actor_role != "human_gate":
                raise StateTransitionError("only human_gate may resolve a gate")
            if decision not in {"approve", "use_fallback", "skip", "cancelled"}:
                raise StateTransitionError("invalid gate decision")
            gate_id = _nonempty_string(payload.get("gate_id"), "payload.gate_id")
            if gate_id not in self.open_gates:
                raise StateTransitionError("gate resolution references no open gate")
            node_id = self._canonical_node_id(event)
            del self.open_gates[gate_id]
            self.gate_resolutions[gate_id] = dict(payload)
            if decision in {"approve", "use_fallback"}:
                self.approved_nodes.add(node_id)
            if decision == "use_fallback":
                self.fallback_nodes.add(node_id)
        elif event_type == "verdict_recorded":
            self._require_published_run(event_type)
            actor = _mapping(event["actor"], "actor")
            # Never trust payload.actor_role or an identity supplied elsewhere.
            actor_role = _nonempty_string(actor.get("role"), "actor.role")
            if actor_role not in {"verifier", "human_gate"}:
                raise StateTransitionError("only verifier or human_gate may publish verdicts")
            raw = payload.get("verdict")
            try:
                verdict = VerdictKind(str(raw))
            except (TypeError, ValueError) as exc:
                raise StateTransitionError(f"invalid verdict: {raw!r}") from exc
            allowed = ({VerdictKind.PASS, VerdictKind.REVISE, VerdictKind.REJECT,
                        VerdictKind.INCONCLUSIVE} if actor_role == "verifier" else
                       {VerdictKind.APPROVE, VerdictKind.REJECT, VerdictKind.INCONCLUSIVE})
            if verdict not in allowed:
                raise StateTransitionError(f"{actor_role} cannot publish {verdict.value}")
            evidence_ids = payload.get("evidence_ids")
            if (not isinstance(evidence_ids, list) or not evidence_ids
                    or any(not isinstance(item, str) or not item.strip() for item in evidence_ids)):
                raise StateTransitionError("evidence_ids must be a non-empty list of non-empty IDs")
            self.verdicts.append(verdict)
            run = self._require_published_run(event_type)
            target_ids = payload.get("target_node_ids")
            if target_ids is None and payload.get("target_node_id") is not None:
                target_ids = [payload["target_node_id"]]
            if target_ids is not None:
                verifier_node_id = self._canonical_node_id(event)
                verifier = run.graph.nodes.get(verifier_node_id)
                if (not isinstance(target_ids, list) or not target_ids
                        or any(not isinstance(item, str) or not item for item in target_ids)):
                    raise StateTransitionError("target_node_ids must be a non-empty string list")
                deterministic = (
                    actor_role == "verifier"
                    and actor.get("role_id") == "role_deterministic_verifier"
                    and target_ids == [verifier_node_id]
                )
                if not deterministic and (verifier is None or verifier.kind is not NodeKind.VERIFIER):
                    raise StateTransitionError("verdict target binding requires a verifier node")
                allowed_targets = {verifier_node_id} if deterministic else {
                    edge.target for edge in run.graph.edges
                    if edge.source == verifier_node_id and str(edge.kind) == "verifies"
                }
                if not set(target_ids) <= allowed_targets:
                    raise StateTransitionError("verifier may only judge its assigned targets")
                target_attempt_ids = payload.get("target_attempt_ids", {})
                if not isinstance(target_attempt_ids, Mapping):
                    raise StateTransitionError("target_attempt_ids must be an object")
                for target_id in target_ids:
                    attempt_id = target_attempt_ids.get(target_id)
                    if attempt_id is not None:
                        if (attempt_id not in self.attempts
                                or self.attempt_nodes[attempt_id] != target_id):
                            raise StateTransitionError("verdict references wrong target attempt")
                    if verdict is VerdictKind.PASS:
                        self._set_node_state(target_id, NodeState.PASSED)
                    elif verdict in {VerdictKind.REVISE, VerdictKind.REJECT}:
                        self._set_node_state(target_id, NodeState.FAILED)
                    elif verdict is VerdictKind.INCONCLUSIVE:
                        self._set_node_state(target_id, NodeState.INCONCLUSIVE)
                self.verdict_targets[event["event_id"]] = tuple(target_ids)
                if (not deterministic and verifier.state in {
                        NodeState.RUNNING, NodeState.AWAITING_VERIFICATION}):
                    self._set_node_state(
                        verifier_node_id,
                        NodeState.PASSED if verdict is VerdictKind.PASS else NodeState.FAILED,
                    )
        elif event_type == "platform_verdict_recorded":
            self._require_published_run(event_type)
            platform = _nonempty_string(payload.get("platform", event.get("platform")), "platform")
            try:
                status = PlatformStatus(payload.get("status"))
            except (TypeError, ValueError) as exc:
                raise StateTransitionError(f"invalid platform status: {payload.get('status')!r}") from exc
            evidence_id = payload.get("evidence_id")
            fixture_id = payload.get("fixture_id")
            snapshot_id = payload.get("snapshot_id")
            if fixture_id is not None:
                fixture_id = _nonempty_string(fixture_id, "fixture_id")
            if snapshot_id is not None:
                snapshot_id = _nonempty_string(snapshot_id, "snapshot_id")
            if status is PlatformStatus.PASS:
                _nonempty_string(evidence_id, "evidence_id")
                if fixture_id is None and snapshot_id is None:
                    raise StateTransitionError("passing platform verdict requires fixture_id or snapshot_id")
            elif evidence_id is not None:
                evidence_id = _nonempty_string(evidence_id, "evidence_id")
            key = "|".join((platform, fixture_id or "", snapshot_id or ""))
            self.platform_verdicts[key] = PlatformVerdict(
                platform, status, evidence_id, str(payload.get("confidence", "unknown")),
                fixture_id, snapshot_id)
        return self

    @property
    def complete_scope(self) -> str | None:
        passing = [v.platform for v in self.platform_verdicts.values()
                   if v.status is PlatformStatus.PASS]
        if not passing:
            return None
        return ",".join(sorted(set(passing)))

    def platform_summary(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for verdict in self.platform_verdicts.values():
            grouped.setdefault(verdict.platform, []).append({
                "status": verdict.status.value, "evidence_id": verdict.evidence_id,
                "confidence": verdict.confidence, "fixture_id": verdict.fixture_id,
                "snapshot_id": verdict.snapshot_id,
            })
        # Preserve the simple one-unit shape while retaining every fixture or
        # snapshot when a platform has multiple verdict units.
        rendered = {name: items[0] if len(items) == 1 else {"verdicts": items}
                    for name, items in sorted(grouped.items())}
        passing = set(self.complete_scope.split(",") if self.complete_scope else ())
        return {"platform_verdicts": rendered, "scope": self.complete_scope,
                "exclusions": sorted(set(grouped) - passing)}


def reduce_event(task: Task, event: Mapping[str, Any]) -> StateReducer:
    return StateReducer(task).apply(event)
