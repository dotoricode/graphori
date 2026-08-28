"""Deterministic, runtime-independent Graphori v2 execution plan."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .run_spec import _reject_unknown, criterion_id
from .model_routing import RoutingDecision
from .skills import SkillBinding


TEAM_IDS = frozenset({"planning", "research", "design", "implementation", "verification"})
TEAM_STATES = frozenset({"standby", "active", "omitted", "blocked", "complete"})
PLAN_STATES = frozenset({"provisional", "committed", "superseded"})


@dataclass(frozen=True)
class TeamSpec:
    team_id: str
    status: str = "standby"
    reason: str = ""

    def __post_init__(self) -> None:
        if self.team_id not in TEAM_IDS:
            raise ValueError(f"unknown team_id: {self.team_id}")
        if self.status not in TEAM_STATES:
            raise ValueError(f"unknown team status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {"team_id": self.team_id, "status": self.status, "reason": self.reason}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TeamSpec":
        _reject_unknown(value, set(cls.__dataclass_fields__), "team")
        return cls(**value)


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    team_id: str
    title: str
    objective: str
    kind: str
    role: str = "worker"
    dependencies: tuple[str, ...] = ()
    read_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    worktree_policy: str = "current"
    provider: str = ""
    provider_family: str = ""
    adapter: str = ""
    model: str = ""
    model_family: str = ""
    effort: str = ""
    fallback_model: str = ""
    fallback_model_family: str = ""
    fallback_provider_family: str = ""
    fallback_adapter: str = ""
    fallback_effort: str = ""
    fallback_approval_class: str = "normal"
    approval_required: bool = False
    approval_class: str = "normal"
    routing_reason_codes: tuple[str, ...] = ()
    routing_decision_digest: str = ""
    routing_confidence: str = "unknown"
    task_kind: str = ""
    synthesis: int = 0
    requires_cross_provider: bool = False
    excluded_provider: str = ""
    adapter_requirements: tuple[str, ...] = ()
    permission_profile: str = "workspace_write"
    skills: tuple[str, ...] = ()
    skill_bindings: tuple[SkillBinding, ...] = ()
    verification_policy: str = "deterministic"
    estimated_startup_ms: int = 0
    estimated_execution_ms: int = 0
    estimated_context_tokens: int = 0
    risk: str = "low"
    uncertainty: int = 0
    reversibility: str = "unknown"
    external_effect: bool = False
    acceptance_criteria: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    reviews_unverified_dependencies: bool = False

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.title.strip() or not self.objective.strip():
            raise ValueError("node_id, title, and objective must be non-empty")
        if self.team_id not in TEAM_IDS:
            raise ValueError(f"unknown team_id: {self.team_id}")
        for name in ("estimated_startup_ms", "estimated_execution_ms",
                     "estimated_context_tokens", "uncertainty", "synthesis"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        for name in ("dependencies", "read_scope", "write_scope", "skills",
                     "routing_reason_codes", "adapter_requirements",
                     "acceptance_criteria", "evidence_requirements"):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))
        criterion_ids = [criterion_id(item) for item in self.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("acceptance criterion IDs must be unique per node")
        object.__setattr__(self, "skill_bindings", tuple(sorted(
            self.skill_bindings, key=lambda item: (item.skill_id, item.digest),
        )))
        binding_ids = [item.skill_id for item in self.skill_bindings]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("skill binding IDs must be unique")
        if len(self.skill_bindings) > 2:
            raise ValueError("a Node may bind at most 2 resolved skills")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if name == "skill_bindings":
                result[name] = [item.to_dict() for item in value]
            else:
                result[name] = list(value) if isinstance(value, tuple) else value
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NodeSpec":
        _reject_unknown(value, set(cls.__dataclass_fields__), "node")
        data = dict(value)
        for name in ("dependencies", "read_scope", "write_scope", "skills",
                     "routing_reason_codes", "adapter_requirements",
                     "acceptance_criteria", "evidence_requirements"):
            data[name] = tuple(data.get(name, ()))
        data["skill_bindings"] = tuple(
            SkillBinding.from_dict(item) for item in data.get("skill_bindings", ())
        )
        return cls(**data)


@dataclass(frozen=True)
class PlanEdge:
    source: str
    target: str
    kind: str = "requires"

    def __post_init__(self) -> None:
        if not self.source or not self.target or self.source == self.target:
            raise ValueError("edge endpoints must be distinct and non-empty")

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "kind": self.kind}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlanEdge":
        _reject_unknown(value, set(cls.__dataclass_fields__), "edge")
        return cls(**value)


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    plan_version: int
    status: str
    teams: tuple[TeamSpec, ...] = ()
    nodes: tuple[NodeSpec, ...] = ()
    edges: tuple[PlanEdge, ...] = ()
    critical_path: tuple[str, ...] = ()
    approval_gates: tuple[str, ...] = ()
    benchmark_snapshot_id: str = ""
    routing_decisions: tuple[RoutingDecision, ...] = ()
    estimated_wall_ms: int | None = None
    estimated_cost_usd: float | None = None
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError(f"unsupported RunPlan schema_version: {self.schema_version}")
        if not self.run_id.strip() or self.plan_version < 1:
            raise ValueError("run_id must be non-empty and plan_version must be positive")
        if self.status not in PLAN_STATES:
            raise ValueError(f"unknown plan status: {self.status}")
        object.__setattr__(self, "teams", tuple(sorted(self.teams, key=lambda item: item.team_id)))
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes, key=lambda item: item.node_id)))
        object.__setattr__(self, "routing_decisions", tuple(sorted(
            self.routing_decisions, key=lambda item: item.node_id,
        )))
        object.__setattr__(self, "edges", tuple(sorted(
            self.edges, key=lambda item: (item.source, item.target, item.kind))))
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node_id values must be unique")
        known = set(node_ids)
        for node in self.nodes:
            missing = set(node.dependencies) - known
            if missing:
                raise ValueError(f"node {node.node_id} has unknown dependencies: {sorted(missing)}")
        remaining = {node.node_id: set(node.dependencies) for node in self.nodes}
        resolved: set[str] = set()
        while remaining:
            ready = sorted(node_id for node_id, dependencies in remaining.items()
                           if dependencies <= resolved)
            if not ready:
                raise ValueError(f"dependency cycle detected: {sorted(remaining)}")
            for node_id in ready:
                resolved.add(node_id)
                del remaining[node_id]
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(f"edge references unknown node: {edge.source}->{edge.target}")
        if set(self.critical_path) - known:
            raise ValueError("critical_path references unknown nodes")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "plan_version": self.plan_version,
            "status": self.status,
            "benchmark_snapshot_id": self.benchmark_snapshot_id,
            "routing_decisions": [item.to_dict() for item in self.routing_decisions],
            "teams": [team.to_dict() for team in self.teams],
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "critical_path": list(self.critical_path),
            "approval_gates": list(self.approval_gates),
            "estimated_wall_ms": self.estimated_wall_ms,
            "estimated_cost_usd": self.estimated_cost_usd,
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunPlan":
        _reject_unknown(value, set(cls.__dataclass_fields__), "RunPlan")
        data = dict(value)
        data["teams"] = tuple(TeamSpec.from_dict(item) for item in data.get("teams", ()))
        data["nodes"] = tuple(NodeSpec.from_dict(item) for item in data.get("nodes", ()))
        data["edges"] = tuple(PlanEdge.from_dict(item) for item in data.get("edges", ()))
        data["routing_decisions"] = tuple(
            RoutingDecision.from_dict(item) for item in data.get("routing_decisions", ())
        )
        for name in ("critical_path", "approval_gates", "assumptions", "unknowns"):
            data[name] = tuple(data.get(name, ()))
        return cls(**data)

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()
