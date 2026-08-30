"""Canonical journal/reducer read model shared by every Graphori consumer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import Edge, EdgeKind, Node, NodeKind, NodeState, Role, Run, Task
from .ports import RuntimeEvent
from .presentation import TEAM_LABELS, presentation_vocabulary
from .reducer import StateReducer
from .run_plan import NodeSpec, RunPlan
from .run_spec import RunSpec, criterion_id
from .scheduler import SchedulingBatch


TEAM_ORDER = ("planning", "research", "design", "implementation", "verification")
TEAM_NAMES = {
    "planning": "Planning",
    "research": "Research",
    "design": "Design",
    "implementation": "Implementation",
    "verification": "Verification",
}
ACTIVE_STATES = frozenset({"ready", "assigned", "running", "awaiting_verification"})
BLOCKED_STATES = frozenset({
    "blocked", "failed", "cancelled", "rejected", "inconclusive", "outcome_unknown",
})
TERMINAL_STATES = frozenset({"passed", "failed", "cancelled", "rejected", "inconclusive"})


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


_UNKNOWN = "unknown"
_LEGACY_TITLE = "Unknown legacy node"


@dataclass(frozen=True)
class ProjectionMetadata:
    """Replay-only metadata plus an explicit account of how it was obtained.

    This is deliberately a projection input, never a journal migration.  A
    legacy default is a documented fixed value required by the v3 model;
    ``unknown`` is reserved for a value the old journal did not record.
    """

    spec: RunSpec
    plan: RunPlan
    provenance: Mapping[str, Any]


def _canonical_value(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _one_metadata_value(values: Sequence[tuple[str, Any]], name: str, parser):
    """Parse repeated metadata only when every supplied value agrees."""

    parsed: list[tuple[str, Any]] = []
    for source, value in values:
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} metadata from {source} must be an object")
        try:
            parsed.append((source, parser(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid {name} metadata from {source}: {exc}") from exc
    if not parsed:
        return None, ()
    canonical = _canonical_value(parsed[0][1].to_dict())
    if any(_canonical_value(item.to_dict()) != canonical for _source, item in parsed[1:]):
        raise ValueError(f"ambiguous {name} metadata sources")
    return parsed[0][1], tuple(source for source, _item in parsed)


def _legacy_projection_metadata(run_id: str, events: Sequence[Mapping[str, Any]]) -> ProjectionMetadata:
    """Make only documented defaults for a journal that has no v3 metadata."""

    versions = {event.get("graph_version") for event in events}
    if len(versions) > 1 or (versions and (not isinstance(next(iter(versions)), int)
                                             or next(iter(versions)) < 1)):
        raise ValueError("legacy journal has ambiguous graph versions")
    plan_version = next(iter(versions), 1)
    node_ids: set[str] = set()
    for event in events:
        entity = event.get("entity") or {}
        payload = event.get("payload") or {}
        entity_node = entity.get("node_id")
        payload_node = payload.get("node_id")
        if entity_node is not None and payload_node is not None and entity_node != payload_node:
            raise ValueError("legacy journal has ambiguous node identity")
        node_id = entity_node if entity_node is not None else payload_node
        if node_id is not None:
            if not isinstance(node_id, str) or not node_id.strip():
                raise ValueError("legacy journal has invalid node identity")
            node_ids.add(node_id)
    finished_roles = replay_node_roles(events)
    plan = RunPlan(
        run_id=run_id,
        plan_version=plan_version,
        status="committed",
        nodes=tuple(NodeSpec(
            node_id=node_id,
            team_id="implementation",
            title=f"{_LEGACY_TITLE}: {node_id}",
            objective=_UNKNOWN,
            kind=finished_roles.get(node_id, "worker"),
            role=finished_roles.get(node_id, "worker"),
        ) for node_id in sorted(node_ids)),
    )
    spec = RunSpec(objective=_UNKNOWN, host=_UNKNOWN, workspace=_UNKNOWN)
    return ProjectionMetadata(
        spec=spec,
        plan=plan,
        provenance={
            "source": "legacy_journal",
            "run_spec": {"source": "unknown", "fields": ["objective", "host", "workspace"]},
            "run_plan": {
                "source": "legacy_default",
                "fields": ["status", "nodes[].team_id", "nodes[].kind", "nodes[].role"],
            },
        },
    )


def resolve_projection_metadata(
        root: Path | str, run_id: str, events: Sequence[Mapping[str, Any]]) -> ProjectionMetadata:
    """Resolve v3 metadata, or deterministically project a wholly legacy journal.

    A partial, malformed, or conflicting v3 declaration is not legacy input:
    it is ambiguous and must fail closed.  This function never writes a
    sidecar or alters the journal bytes/hash chain.
    """

    run_root = Path(root) / ".graphori" / "runs" / run_id
    values: dict[str, list[tuple[str, Any]]] = {"run_spec": [], "plan": []}
    for filename, key in (("run-spec.json", "run_spec"), ("run-plan.json", "plan")):
        path = run_root / filename
        if path.exists():
            try:
                values[key].append((filename, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid {key} sidecar: {exc}") from exc
    for event in events:
        payload = event.get("payload") or {}
        for key in values:
            if key in payload:
                values[key].append((f"event:{event.get('seq')}", payload[key]))

    has_any_v3_metadata = any(values.values())
    spec, spec_sources = _one_metadata_value(values["run_spec"], "RunSpec", RunSpec.from_dict)
    plan, plan_sources = _one_metadata_value(values["plan"], "RunPlan", RunPlan.from_dict)
    if has_any_v3_metadata:
        if spec is None or plan is None:
            raise ValueError("partial canonical dashboard metadata is ambiguous")
        if plan.run_id != run_id:
            raise ValueError("dashboard RunPlan identity mismatch")
        versions = {event.get("graph_version") for event in events}
        if versions and (len(versions) != 1 or plan.plan_version not in versions):
            raise ValueError("canonical metadata graph version mismatch")
        return ProjectionMetadata(
            spec=spec,
            plan=plan,
            provenance={
                "source": "canonical_v3",
                "run_spec": {"source": "recorded", "sources": list(spec_sources)},
                "run_plan": {"source": "recorded", "sources": list(plan_sources)},
            },
        )
    return _legacy_projection_metadata(run_id, events)


def _milliseconds(start: str | None, finish: str | None) -> int | None:
    if not start or not finish:
        return None
    try:
        left = datetime.fromisoformat(start.replace("Z", "+00:00"))
        right = datetime.fromisoformat(finish.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return max(0, round((right - left).total_seconds() * 1000))


def replay_task_id(events: Sequence[Mapping[str, Any]], *, default: str) -> str:
    """Return the one recorded task identity, rejecting an ambiguous history."""

    task_ids = {(event.get("entity") or {}).get("task_id") for event in events}
    if not task_ids:
        return default
    if len(task_ids) != 1 or not isinstance(next(iter(task_ids)), str):
        raise ValueError("journal has ambiguous task identity")
    return next(iter(task_ids))


def _replay_finished_node_actors(events: Sequence[Mapping[str, Any]]) -> Mapping[str, tuple[str, str]]:
    """Read actor identities only where the journal explicitly binds them."""

    values: dict[str, tuple[str, str]] = {}
    for event in events:
        if event.get("type") != "worker_finished":
            continue
        entity = event.get("entity") or {}
        payload = event.get("payload") or {}
        node_id = entity.get("node_id", payload.get("node_id"))
        actor = event.get("actor") or {}
        role_id = actor.get("role_id")
        role = actor.get("role")
        if (not isinstance(node_id, str) or not node_id or not isinstance(role_id, str)
                or not role_id or role not in {"worker", "verifier"}):
            raise ValueError("legacy journal has invalid worker role identity")
        existing = values.setdefault(node_id, (role, role_id))
        if existing != (role, role_id):
            raise ValueError("legacy journal has ambiguous worker role identity")
    return values


def replay_node_role_ids(events: Sequence[Mapping[str, Any]]) -> Mapping[str, str]:
    return {node_id: role_id for node_id, (_role, role_id)
            in _replay_finished_node_actors(events).items()}


def replay_node_roles(events: Sequence[Mapping[str, Any]]) -> Mapping[str, str]:
    return {node_id: role for node_id, (role, _role_id)
            in _replay_finished_node_actors(events).items()}


def fresh_reducer(plan: RunPlan, *, task_id: str | None = None,
                  node_role_ids: Mapping[str, str] | None = None) -> StateReducer:
    """Create the reducer topology used for live execution and cold replay."""

    task = Task(
        task_id or f"task:{plan.run_id}", plan.run_id, run_id=plan.run_id,
        graph_version=plan.plan_version,
    )
    run = Run(plan.run_id, graph_version=plan.plan_version)
    for spec in plan.nodes:
        try:
            kind = NodeKind(spec.kind)
        except ValueError:
            kind = NodeKind.WORKER
        actor_kind = NodeKind.VERIFIER if kind is NodeKind.VERIFIER else NodeKind.WORKER
        role_name = "verifier" if kind is NodeKind.VERIFIER else "worker"
        role_id = (node_role_ids or {}).get(spec.node_id, f"role_{role_name}_{spec.node_id}")
        run.graph.add_node(Node(
            spec.node_id, kind, spec.title,
            role=Role(role_id, actor_kind,
                      f"{role_name}:{spec.node_id}"),
        ))
    for spec in plan.nodes:
        edge_kind = EdgeKind.VERIFIES if spec.kind == "verifier" else EdgeKind.REQUIRES
        for dependency in spec.dependencies:
            run.graph.add_edge(Edge(spec.node_id, dependency, edge_kind))
    return StateReducer(task, run)


def effective_plan(plan: RunPlan, events: Sequence[Mapping[str, Any]]) -> RunPlan:
    """Apply canonical fallback/rework identities without mutating published history."""

    nodes = {node.node_id: node for node in plan.nodes}
    for event in events:
        payload = event.get("payload") or {}
        entity = event.get("entity") or {}
        if event.get("type") == "gate_resolved" and payload.get("decision") == "use_fallback":
            node_id = str(entity.get("node_id", ""))
            node = nodes.get(node_id)
            if node is not None:
                nodes[node_id] = replace(
                    node,
                    provider=node.fallback_adapter or node.provider,
                    provider_family=node.fallback_provider_family,
                    adapter=node.fallback_adapter,
                    model=node.fallback_model,
                    model_family=node.fallback_model_family,
                    effort=node.fallback_effort,
                    approval_required=False,
                    approval_class="normal",
                )
            continue
        if event.get("type") != "rework_created":
            continue
        original = nodes.get(str(entity.get("node_id", "")))
        verifier = nodes.get(str(payload.get("verifier_node_id", "")))
        if original is None or verifier is None:
            continue
        rework_id = str(payload["rework_node_id"])
        verifier_id = str(payload["rework_verifier_node_id"])
        nodes[rework_id] = replace(original, node_id=rework_id,
                                   title=f"{original.title} (rework)")
        nodes[verifier_id] = replace(
            verifier, node_id=verifier_id, title=f"{verifier.title} (rework)",
            dependencies=(rework_id,),
        )
        nodes[original.node_id] = replace(original, closes_proofs=())
        nodes[verifier.node_id] = replace(verifier, closes_proofs=())
    return replace(plan, nodes=tuple(nodes.values()))


@dataclass(frozen=True)
class CanonicalRunProjection:
    """Stable read contract; UI labels may change but these meanings may not."""

    run_id: str
    plan_digest: str
    node_states: Mapping[str, str]
    terminal_status: str | None
    events: tuple[RuntimeEvent, ...] = ()
    attempt_states: Mapping[str, str] = field(default_factory=dict)
    retry_counts: Mapping[str, int] = field(default_factory=dict)
    rework_counts: Mapping[str, int] = field(default_factory=dict)
    open_gates: Mapping[str, str] = field(default_factory=dict)
    active_wip: int = 0
    ready: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    projection_digest: str = ""
    runtime_bindings: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    resource_dispositions: Mapping[str, str] = field(default_factory=dict)
    gate_records: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    gate_resolutions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    approved_nodes: frozenset[str] = frozenset()
    routing_observations: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    skill_bindings: Mapping[str, tuple[Mapping[str, Any], ...]] = field(default_factory=dict)
    schema_version: int = 3
    objective: str = ""
    status: str = "planning"
    plan_version: int = 1
    journal_digest: str = ""
    graph_digest: str = ""
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    risk_level: str = "low"
    terminal_reason: str | None = None
    teams: tuple[Mapping[str, Any], ...] = ()
    nodes: tuple[Mapping[str, Any], ...] = ()
    edges: tuple[Mapping[str, Any], ...] = ()
    attempts: tuple[Mapping[str, Any], ...] = ()
    gates: tuple[Mapping[str, Any], ...] = ()
    actors: tuple[Mapping[str, Any], ...] = ()
    assignments: tuple[Mapping[str, Any], ...] = ()
    available_routes: tuple[Mapping[str, Any], ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    verification: Mapping[str, Any] = field(default_factory=dict)
    recent_events: tuple[Mapping[str, Any], ...] = ()
    metadata_provenance: Mapping[str, Any] = field(default_factory=dict)
    snapshot_seq: int = 0
    updated_at: str | None = None
    last_heartbeat_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        completed = sum(node.get("status") == "passed" for node in self.nodes)
        required = len(self.nodes)
        return {
            "schema_version": self.schema_version,
            "projection_digest": self.projection_digest,
            "run_id": self.run_id,
            "objective": self.objective,
            "status": self.status,
            "state": self.status,
            "terminal_status": self.terminal_status,
            "terminal_reason": self.terminal_reason,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "updatedAt": self.updated_at,
            "risk_level": self.risk_level,
            "plan_version": self.plan_version,
            "plan_digest": self.plan_digest,
            "journal_digest": self.journal_digest,
            "graph_digest": self.graph_digest,
            "snapshot_seq": self.snapshot_seq,
            "active_wip": self.active_wip,
            "actual_agent_count": len(self.actors),
            "active_agent_count": sum(bool(item.get("active")) for item in self.assignments),
            "ready": list(self.ready),
            "blocked": list(self.blocked),
            "teams": [dict(item) for item in self.teams],
            "nodes": [dict(item) for item in self.nodes],
            "edges": [dict(item) for item in self.edges],
            "attempts": [dict(item) for item in self.attempts],
            "gates": [dict(item) for item in self.gates],
            "actors": [dict(item) for item in self.actors],
            "assignments": [dict(item) for item in self.assignments],
            "available_routes": [dict(item) for item in self.available_routes],
            "metrics": dict(self.metrics),
            "verification": dict(self.verification),
            # This records read-time compatibility provenance.  It is not a
            # journal claim and is intentionally outside projection_digest.
            "metadata_provenance": dict(self.metadata_provenance),
            "recentEvents": [dict(item) for item in self.recent_events],
            "lastEvent": dict(self.recent_events[-1]) if self.recent_events else None,
            "progress": {
                "completed": completed, "required": required,
                "percent": round(completed * 100 / required) if required else 0,
                "basis": "verified_terminal_nodes",
            },
            "presentation": presentation_vocabulary(),
            "attempt_states": dict(self.attempt_states),
            "retry_counts": dict(self.retry_counts),
            "rework_counts": dict(self.rework_counts),
            "open_gates": dict(self.open_gates),
            "runtime_bindings": {key: dict(value) for key, value in self.runtime_bindings.items()},
            "resource_dispositions": dict(self.resource_dispositions),
            "gate_records": {key: dict(value) for key, value in self.gate_records.items()},
            "gate_resolutions": {key: dict(value) for key, value in self.gate_resolutions.items()},
            "routing_observations": {
                key: dict(value) for key, value in self.routing_observations.items()
            },
            "skill_bindings": {
                key: [dict(item) for item in value]
                for key, value in self.skill_bindings.items()
            },
        }


def _event_view(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    entity = event.get("entity") or {}
    actor = event.get("actor") or {}
    evidence = payload.get("evidence_ids")
    if evidence is None and payload.get("evidence_id"):
        evidence = [payload["evidence_id"]]
    return {
        "event_id": event.get("event_id"),
        "producer_event_id": event.get("producer_event_id"),
        "seq": event.get("seq"),
        "type": event.get("type"),
        "node_id": entity.get("node_id") or payload.get("node_id"),
        "attempt_id": entity.get("attempt_id") or payload.get("attempt_id"),
        "role": actor.get("role"),
        "producer": {"role": actor.get("role"), "role_id": actor.get("role_id")},
        "summary": (payload.get("summary") or payload.get("current_task")
                    or payload.get("description") or payload.get("task")),
        "updatedAt": event.get("recorded_at") or event.get("occurred_at"),
        "digest": event.get("digest"),
        "evidence_ids": list(evidence or ()),
        "payload": dict(payload),
    }


def _criterion_evidence(node: NodeSpec, history: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Project criterion proof without treating a worker self-report as proof."""
    results = {criterion_id(item): {
        "criterion_id": criterion_id(item), "criterion": item,
        "status": "NOT_PROVEN", "source": "none", "evidence_ids": [],
    } for item in node.acceptance_criteria}
    for event in history:
        payload = event.get("payload") or {}
        source = str((event.get("actor") or {}).get("role") or "unknown")
        reports = payload.get("criterion_evidence")
        if not isinstance(reports, Mapping):
            continue
        for identifier, claim in reports.items():
            item = results.get(str(identifier))
            if item is None or not isinstance(claim, Mapping):
                continue
            status = str(claim.get("status", "NOT_PROVEN")).upper()
            evidence_ids = [str(value) for value in claim.get("evidence_ids", ())]
            criterion_command = any(
                value.startswith("subprocess:criterion-command:") for value in evidence_ids
            )
            mapped_command = (
                f"criterion:{identifier}" in node.evidence_requirements
                and any(value.startswith(
                    f"subprocess:criterion-command:{identifier}:"
                ) for value in evidence_ids)
            )
            # A Worker self-report is never proof. Process-boundary criteria
            # need evidence from the test itself, not merely the verifier
            # command's own process exit.
            if status == "PROVEN" and source not in {"verifier", "coordinator", "independent_verifier"}:
                status = "NOT_PROVEN"
            if status == "PROVEN" and criterion_command and not mapped_command:
                status = "NOT_PROVEN"
            criterion_text = str(item["criterion"]).casefold()
            requires_process_boundary = any(token in criterion_text for token in (
                "subprocess", "cold process", "cold-process", "별도 프로세스",
            ))
            if (status == "PROVEN" and requires_process_boundary
                    and not (
                        any(value.startswith("subprocess:test:") for value in evidence_ids)
                        or mapped_command
                    )):
                status = "NOT_PROVEN"
            if status not in {"PROVEN", "NOT_PROVEN", "FAILED", "NOT_APPLICABLE"}:
                status = "NOT_PROVEN"
            item.update(status=status, source=source, evidence_ids=evidence_ids)
    return [results[key] for key in sorted(results)]


def _usage_summary(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Expose only provider-reported token buckets; absent values stay unknown."""
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "new_input_tokens": 0}
    known = False
    for event in events:
        event_usage = event.get("usage")
        runtime_usage = ((event.get("payload") or {}).get("runtime_metadata") or {}).get("usage")
        usage = runtime_usage if isinstance(runtime_usage, Mapping) else event_usage
        if not isinstance(usage, Mapping):
            continue
        raw_input = usage.get("input_tokens", usage.get("input", usage.get("total_input_tokens")))
        raw_cached = usage.get("cached_input_tokens", usage.get("cached_tokens", usage.get("input_tokens_cached")))
        if not isinstance(raw_input, int) or raw_input < 0:
            continue
        cached = raw_cached if isinstance(raw_cached, int) and 0 <= raw_cached <= raw_input else None
        totals["input_tokens"] += raw_input
        if cached is not None:
            totals["cached_input_tokens"] += cached
            totals["new_input_tokens"] += raw_input - cached
        known = True
    if not known:
        return {"status": "unknown", "input_tokens": None, "cached_input_tokens": None,
                "new_input_tokens": None}
    return {"status": "known", **totals}


def build_canonical_projection(
        *, spec: RunSpec, published_plan: RunPlan, plan: RunPlan,
        reducer: StateReducer, events: Sequence[Mapping[str, Any]],
        journal_digest: str, scheduling: SchedulingBatch) -> CanonicalRunProjection:
    """Build the only authoritative read model from reducer state and its plan."""

    if reducer.run is None:
        raise ValueError("canonical projection requires a replayed Run")
    node_states = {
        node_id: node.state.value for node_id, node in sorted(reducer.run.graph.nodes.items())
    }
    attempts = {
        attempt_id: attempt.state.value for attempt_id, attempt in sorted(reducer.attempts.items())
    }
    event_by_node: dict[str, list[Mapping[str, Any]]] = {}
    published_skills: Mapping[str, list[Mapping[str, Any]]] = {}
    published_route_health: Sequence[Mapping[str, Any]] = ()
    terminal_reason = None
    for event in events:
        entity = event.get("entity") or {}
        payload = event.get("payload") or {}
        node_id = entity.get("node_id") or payload.get("node_id")
        if node_id:
            event_by_node.setdefault(str(node_id), []).append(event)
        if event.get("type") == "graph_published" and isinstance(payload.get("skill_bindings"), Mapping):
            published_skills = payload["skill_bindings"]
        if event.get("type") == "graph_published" and isinstance(payload.get("route_health"), list):
            published_route_health = tuple(
                item for item in payload["route_health"] if isinstance(item, Mapping)
            )
        if event.get("type") == "run_terminal":
            terminal_reason = payload.get("reason") or payload.get("blocking_reason")

    edge_values: list[dict[str, str]] = []
    for node in plan.nodes:
        for dependency in node.dependencies:
            edge_values.append({
                "from": dependency, "to": node.node_id,
                "type": "verifies" if node.kind == "verifier" else "requires",
            })
    for edge in plan.edges:
        candidate = {"from": edge.source, "to": edge.target, "type": edge.kind}
        if candidate not in edge_values:
            edge_values.append(candidate)
    edge_values.sort(key=lambda item: (item["from"], item["to"], item["type"]))
    graph_digest = _stable_digest({
        "plan_version": plan.plan_version,
        "nodes": [node.node_id for node in plan.nodes],
        "edges": edge_values,
    })

    dependents: dict[str, list[str]] = {node.node_id: [] for node in plan.nodes}
    for edge in edge_values:
        dependents.setdefault(edge["from"], []).append(edge["to"])

    verdict_by_target: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "verdict_recorded":
            continue
        payload = event.get("payload") or {}
        targets = payload.get("target_node_ids") or (
            [payload["target_node_id"]] if payload.get("target_node_id") else []
        )
        for target in targets:
            verdict_by_target[str(target)] = {
                "status": payload.get("verdict"),
                "source": str((event.get("actor") or {}).get("role") or "unknown"),
                "event_id": event.get("event_id"),
                "evidence_ids": list(payload.get("evidence_ids") or ()),
                "recorded_at": event.get("recorded_at") or event.get("occurred_at"),
            }

    node_values: list[dict[str, Any]] = []
    verification_values: dict[str, Any] = {}
    for node in plan.nodes:
        history = event_by_node.get(node.node_id, [])
        first = history[0] if history else None
        assigned = next((item for item in history if item.get("type") == "node_status_changed"
                         and (item.get("payload") or {}).get("status") == "assigned"), None)
        running = next((item for item in history if item.get("type") == "node_status_changed"
                        and (item.get("payload") or {}).get("status") == "running"), None)
        finished = next((item for item in reversed(history)
                         if item.get("type") == "worker_finished"), None)
        verdict = verdict_by_target.get(node.node_id)
        last = history[-1] if history else None
        started_at = ((running or assigned or first) or {}).get("recorded_at")
        finished_at = ((verdict or {}).get("recorded_at")
                       or ((finished or {}).get("recorded_at")))
        finished_payload = (finished or {}).get("payload") or {}
        observed = reducer.routing_observations.get(node.node_id, {})
        result_metrics = finished_payload.get("metrics") or {}
        skills = tuple(dict(item) for item in published_skills.get(
            node.node_id, [binding.to_dict() for binding in node.skill_bindings],
        ))
        evidence_ids: list[str] = []
        for item in history:
            payload = item.get("payload") or {}
            evidence_ids.extend(str(value) for value in payload.get("evidence_ids") or ())
        verification = verdict or {
            "status": "pending" if node_states.get(node.node_id) == "awaiting_verification"
            else "not_required" if node.verification_policy == "deterministic"
            else "not_started",
            "event_id": None, "evidence_ids": [], "recorded_at": None,
        }
        verification_values[node.node_id] = verification
        criteria = _criterion_evidence(node, [
            *history,
            *(event for event in events if event.get("type") == "verdict_recorded"
              and node.node_id in ((event.get("payload") or {}).get("target_node_ids") or ())),
        ])
        node_values.append({
            "node_id": node.node_id,
            "id": node.node_id,
            "team_id": node.team_id,
            "kind": node.kind,
            "role": node.role,
            "title": node.title,
            "display_title": node.title,
            "objective": node.objective,
            "current_task": node.title,
            "status": node_states.get(node.node_id, "pending"),
            "scheduler_status": (
                "blocked" if node.node_id in scheduling.blocked else
                "ready" if node.node_id in scheduling.ready else
                "waiting" if node.node_id in scheduling.waiting else None
            ),
            "dependencies": list(node.dependencies),
            "dependents": sorted(dependents.get(node.node_id, ())),
            "provider": node.provider_family or node.provider,
            "adapter": node.adapter or node.provider,
            "selected_route": node.adapter or node.provider,
            "requested_model": node.model or None,
            "observed_model": observed.get("observed_model"),
            "requested_effort": node.effort or None,
            "observed_effort": observed.get("observed_effort"),
            "model": node.model or None,
            "effort": node.effort or None,
            "skills": [dict(item) for item in skills],
            "attempt_count": sum(value == node.node_id for value in reducer.attempt_nodes.values()),
            "read_scope": list(node.read_scope),
            "write_scope": list(node.write_scope),
            "approval_required": node.approval_required,
            "approval_status": next((
                "pending" if gate_id in reducer.open_gates else
                str(reducer.gate_resolutions.get(gate_id, {}).get("decision", "resolved"))
                for gate_id, record in reducer.gate_records.items()
                if ((record.get("approval_envelope") or {}).get("node_id") == node.node_id)
            ), None),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": _milliseconds(started_at, finished_at),
            "timing": {
                "queued_ms": (observed.get("queue_ms")
                              if observed.get("queue_ms") is not None else _milliseconds(
                                  (events[0].get("recorded_at") if events else None),
                                  started_at)),
                "startup_ms": (observed.get("startup_ms")
                                if observed.get("startup_ms") is not None else _milliseconds(
                                    (assigned or {}).get("recorded_at"),
                                    (running or {}).get("recorded_at"))),
                "execution_ms": (observed.get("execution_ms")
                                  if observed.get("execution_ms") is not None else _milliseconds(
                                      (running or assigned or {}).get("recorded_at"),
                                      (finished or {}).get("recorded_at"))),
                "collect_ms": result_metrics.get("collect_ms"),
                "verification_ms": _milliseconds(
                    (finished or {}).get("recorded_at"), (verdict or {}).get("recorded_at")),
                "total_ms": (observed.get("total_ms")
                             if observed.get("total_ms") is not None
                             else _milliseconds(started_at, finished_at)),
            },
            "execution": {
                "status": finished_payload.get("outcome", "not_started"),
                "source": str((finished or {}).get("actor", {}).get("role") or "not_recorded"),
                "worker_report": finished_payload.get("worker_report_status"),
                "finished_at": (finished or {}).get("recorded_at"),
            },
            "verification": dict(verification),
            "verification_source": (
                str(verdict.get("source")) if verdict else "not_recorded"
            ),
            "criteria": criteria,
            "verdict": verification.get("status", "pending"),
            "evidence_ids": sorted(set(evidence_ids)),
            "last_event": _event_view(last) if last else None,
        })

    teams: list[dict[str, Any]] = []
    declared = {team.team_id: team for team in published_plan.teams}
    for team_id in TEAM_ORDER:
        team_nodes = [item for item in node_values if item["team_id"] == team_id]
        states = [item["status"] for item in team_nodes]
        ready_nodes = {
            item["node_id"] for item in team_nodes
            if item["node_id"] in scheduling.ready
        }
        if team_id == "planning":
            status = "complete" if reducer.run.terminal_status is not None else "active"
        elif not team_nodes:
            status = "omitted"
        elif (any(state in BLOCKED_STATES for state in states)
              or any(item["node_id"] in scheduling.blocked for item in team_nodes)):
            status = "blocked"
        elif states and all(state == "passed" for state in states):
            status = "complete"
        elif ready_nodes or any(state in ACTIVE_STATES for state in states):
            status = "active"
        else:
            status = "standby"
        teams.append({
            "team_id": team_id,
            "display_name": TEAM_NAMES[team_id],
            "presentation": dict(TEAM_LABELS[team_id]),
            "status": status,
            "role": "coordinator" if team_id == "planning" else "team",
            "agent_count": 0 if team_id == "planning" else sum(
                reducer.attempt_nodes.get(attempt_id) in {item["node_id"] for item in team_nodes}
                for attempt_id in reducer.attempts
            ),
            "active_node_count": sum(state in ACTIVE_STATES for state in states) + len(ready_nodes),
            "total_node_count": len(team_nodes),
            "reason": declared.get(team_id).reason if team_id in declared else "",
        })

    attempt_values = []
    actor_values = []
    assignments = []
    for attempt_id, attempt in sorted(reducer.attempts.items()):
        node_id = reducer.attempt_nodes.get(attempt_id, "")
        state = attempt.state.value
        actor_id = f"actor:{attempt_id}"
        attempt_values.append({
            "attempt_id": attempt_id, "node_id": node_id, "status": state,
            "retry_of": attempt.retry_of, "actor_id": actor_id,
        })
        actor_values.append({
            "actor_id": actor_id, "role_id": attempt.actor.role_id,
            "role": attempt.actor.role.value,
            "provider": next((item["provider"] for item in node_values
                              if item["node_id"] == node_id), None),
            "model": next((item["model"] for item in node_values
                           if item["node_id"] == node_id), None),
            "attempt_id": attempt_id,
        })
        assignments.append({
            "actor_id": actor_id, "attempt_id": attempt_id, "node_id": node_id,
            "active": state in {"dispatched", "running"},
        })

    gates = []
    for gate_id, record in sorted(reducer.gate_records.items()):
        approval = record.get("approval_envelope") or {}
        resolution = reducer.gate_resolutions.get(gate_id, {})
        gates.append({
            "gate_id": gate_id,
            "node_id": approval.get("node_id"),
            "kind": record.get("kind"),
            "question": record.get("question"),
            "options": list(record.get("options") or ("approve", "use_fallback", "skip")),
            "status": "pending" if gate_id in reducer.open_gates else "resolved",
            "decision": resolution.get("decision"),
            "requested_model": approval.get("model_family"),
            "requested_effort": approval.get("max_effort"),
        })

    terminal = reducer.run.terminal_status.value if reducer.run.terminal_status else None
    if terminal:
        status = terminal
    elif reducer.open_gates:
        status = "waiting_approval"
    elif any(state == "outcome_unknown" for state in node_states.values()):
        status = "outcome_unknown"
    elif any(state in {"blocked", "failed"} for state in node_states.values()):
        status = "blocked"
    elif events:
        status = "running"
    else:
        status = "planning"

    recent = tuple(_event_view(item) for item in events[-40:])
    runtime_events = tuple(RuntimeEvent(
        str(event.get("type", "")), str((event.get("entity") or {}).get("node_id", "")),
        str((event.get("actor") or {}).get("role", "")), dict(event.get("payload") or {}),
        event_id=str(event.get("event_id", "")),
        producer_event_id=str(event.get("producer_event_id", "")),
        actor_role_id=str((event.get("actor") or {}).get("role_id", "")),
        occurred_at=str(event.get("occurred_at", "")),
    ) for event in events)
    routes = sorted({
        (node.adapter or node.provider, node.provider_family or node.provider)
        for node in plan.nodes if node.adapter or node.provider
    })
    route_values = tuple(dict(item) for item in published_route_health) or tuple({
        "route": adapter, "provider": provider, "health": "ready",
        "source": "run_prepare", "selected": True,
    } for adapter, provider in routes)
    active_wip = sum(state in {"assigned", "running", "stale", "outcome_unknown"}
                     for state in node_states.values())
    created_at = events[0].get("recorded_at") if events else None
    started_at = next((event.get("recorded_at") for event in events
                       if event.get("type") == "attempt_dispatched"), created_at)
    finished_at = next((event.get("recorded_at") for event in reversed(events)
                        if event.get("type") == "run_terminal"), None)
    updated_at = events[-1].get("recorded_at") if events else None
    heartbeat_at = next((event.get("recorded_at") for event in reversed(events)
                         if event.get("type") == "heartbeat"), None)
    attempt_states = dict(attempts)
    skill_bindings = {
        str(node_id): tuple(dict(item) for item in bindings)
        for node_id, bindings in sorted(published_skills.items())
    }
    criterion_values: dict[str, dict[str, Any]] = {}
    criterion_priority = {
        "NOT_APPLICABLE": 0, "NOT_PROVEN": 1, "PROVEN": 2, "FAILED": 3,
    }
    for node in node_values:
        for criterion in node.get("criteria", ()):
            identifier = str(criterion.get("criterion_id", ""))
            current = criterion_values.get(identifier)
            if current is None or criterion_priority.get(
                    str(criterion.get("status")), 1) > criterion_priority.get(
                        str(current.get("status")), 1):
                criterion_values[identifier] = dict(criterion)
    acceptance_values = [criterion_values[key] for key in sorted(criterion_values)]
    if not acceptance_values:
        requirements_status = "not_declared"
    elif any(item["status"] == "FAILED" for item in acceptance_values):
        requirements_status = "failed"
    elif all(item["status"] in {"PROVEN", "NOT_APPLICABLE"} for item in acceptance_values):
        requirements_status = "proven"
    else:
        requirements_status = "not_proven"
    verification_summary = {
        "nodes": verification_values,
        "acceptance_criteria": acceptance_values,
        "requirements_status": requirements_status,
        **reducer.platform_summary(),
    }
    base = {
        "run_id": published_plan.run_id,
        "objective": spec.objective,
        "status": status,
        "terminal_status": terminal,
        "terminal_reason": terminal_reason,
        "plan_version": published_plan.plan_version,
        "plan_digest": published_plan.digest(),
        "journal_digest": journal_digest,
        "graph_digest": graph_digest,
        "node_states": node_states,
        "attempt_states": attempt_states,
        "retry_counts": dict(sorted(reducer.retry_counts.items())),
        "rework_counts": dict(sorted(reducer.rework_counts.items())),
        "open_gates": dict(sorted(reducer.open_gates.items())),
        "ready": list(scheduling.ready),
        "blocked": list(scheduling.blocked),
        "active_wip": active_wip,
        "runtime_bindings": {key: dict(value) for key, value in sorted(reducer.runtime_bindings.items())},
        "resource_dispositions": dict(sorted(reducer.resource_dispositions.items())),
        "gate_records": {key: dict(value) for key, value in sorted(reducer.gate_records.items())},
        "gate_resolutions": {key: dict(value) for key, value in sorted(reducer.gate_resolutions.items())},
        "routing_observations": {key: dict(value) for key, value in sorted(reducer.routing_observations.items())},
        "skill_bindings": {key: [dict(item) for item in value] for key, value in skill_bindings.items()},
        "teams": teams, "nodes": node_values, "edges": edge_values,
        "attempts": attempt_values, "gates": gates,
        "actors": actor_values, "assignments": assignments,
        "available_routes": list(route_values),
        "verification": verification_summary,
        "metrics": {
            "active_wip": active_wip,
            "node_total": len(node_values),
            "node_passed": sum(item["status"] == "passed" for item in node_values),
            "usage": _usage_summary(events),
        },
        "snapshot_seq": int(events[-1].get("seq", 0)) if events else 0,
        "created_at": created_at, "started_at": started_at,
        "finished_at": finished_at, "updated_at": updated_at,
        "last_heartbeat_at": heartbeat_at,
    }
    return CanonicalRunProjection(
        run_id=published_plan.run_id,
        plan_digest=published_plan.digest(),
        node_states=node_states,
        terminal_status=terminal,
        events=runtime_events,
        attempt_states=attempt_states,
        retry_counts=dict(reducer.retry_counts),
        rework_counts=dict(reducer.rework_counts),
        open_gates=dict(reducer.open_gates),
        active_wip=active_wip,
        ready=scheduling.ready,
        blocked=scheduling.blocked,
        projection_digest=_stable_digest(base),
        runtime_bindings=dict(reducer.runtime_bindings),
        resource_dispositions=dict(reducer.resource_dispositions),
        gate_records=dict(reducer.gate_records),
        gate_resolutions=dict(reducer.gate_resolutions),
        approved_nodes=frozenset(reducer.approved_nodes),
        routing_observations=dict(reducer.routing_observations),
        skill_bindings=skill_bindings,
        objective=spec.objective,
        status=status,
        plan_version=published_plan.plan_version,
        journal_digest=journal_digest,
        graph_digest=graph_digest,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        risk_level=max(
            (node.risk for node in plan.nodes), default="low",
            key=lambda value: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(value, 0),
        ),
        terminal_reason=terminal_reason,
        teams=tuple(teams), nodes=tuple(node_values), edges=tuple(edge_values),
        attempts=tuple(attempt_values), gates=tuple(gates),
        actors=tuple(actor_values), assignments=tuple(assignments),
        available_routes=route_values,
        metrics=base["metrics"], verification=verification_summary,
        recent_events=recent,
        snapshot_seq=base["snapshot_seq"], updated_at=updated_at,
        last_heartbeat_at=heartbeat_at,
    )


RunProjection = CanonicalRunProjection


__all__ = [
    "CanonicalRunProjection", "RunProjection", "build_canonical_projection",
    "ProjectionMetadata", "effective_plan", "fresh_reducer", "replay_node_role_ids",
    "replay_node_roles", "replay_task_id",
    "resolve_projection_metadata",
]
