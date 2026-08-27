"""Deterministic, latency-first model routing with explicit premium policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class ApprovalClass(str, Enum):
    NORMAL = "normal"
    PREMIUM = "premium"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class RoutingMode(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


@dataclass(frozen=True)
class RuntimeModel:
    provider: str
    adapter: str
    runtime_model_id: str
    family: str
    effort_levels: tuple[str, ...]
    availability: Availability
    approval_class: ApprovalClass
    capabilities: tuple[str, ...] = ()
    reliability_prior: float | None = None

    def __post_init__(self) -> None:
        if not all((self.provider, self.adapter, self.runtime_model_id, self.family)):
            raise ValueError("runtime model identities must be explicit")
        object.__setattr__(self, "effort_levels", tuple(dict.fromkeys(self.effort_levels)))
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))


@dataclass(frozen=True)
class BenchmarkModel:
    benchmark_model_id: str
    family: str
    effort: str
    coding_index: float | None
    expected_wall_ms: int | None
    cost_per_task_usd: float | None = None
    benchmark_confidence: str = "unknown"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkModel":
        return cls(**value)


@dataclass(frozen=True)
class BenchmarkCatalog:
    source: str
    source_url: str
    benchmark_version: str
    retrieved_at: str
    source_digest: str
    quality_equivalence_margin: float
    models: tuple[BenchmarkModel, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkCatalog":
        data = dict(value)
        data["models"] = tuple(BenchmarkModel.from_dict(item) for item in data["models"])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "benchmark_version": self.benchmark_version,
            "retrieved_at": self.retrieved_at,
            "source_digest": self.source_digest,
            "quality_equivalence_margin": self.quality_equivalence_margin,
            "models": [asdict(item) for item in self.models],
        }

    @property
    def snapshot_digest(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_benchmark_snapshot(path: Path | None = None) -> BenchmarkCatalog:
    source = path or Path(__file__).with_name("model_data") / "coding-agent-index-v1.3.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("benchmark snapshot must be an object")
    body = {key: item for key, item in value.items() if key != "source_digest"}
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if value.get("source_digest") != expected:
        raise ValueError("benchmark snapshot source_digest mismatch")
    return BenchmarkCatalog.from_dict(value)


@dataclass(frozen=True)
class ModelBenchmarkBinding:
    benchmark_model_id: str
    runtime_model_id: str
    effort: str
    confidence: str


@dataclass(frozen=True)
class ProviderCatalog:
    models: tuple[RuntimeModel, ...]

    def __post_init__(self) -> None:
        identities = [item.runtime_model_id for item in self.models]
        if len(identities) != len(set(identities)):
            raise ValueError("runtime_model_id values must be unique")


@dataclass(frozen=True)
class RoutingTelemetryRecord:
    routing_decision_id: str
    requested_model: str
    observed_model: str
    requested_effort: str
    observed_effort: str
    queue_ms: int
    startup_ms: int
    execution_ms: int
    total_ms: int
    outcome: str
    verification_outcome: str = "unknown"
    rework_required: bool = False


@dataclass(frozen=True)
class LocalTelemetrySnapshot:
    sample_counts: Mapping[str, int] = field(default_factory=dict)
    confidence: str = "unknown"
    records: tuple[RoutingTelemetryRecord, ...] = ()

    @classmethod
    def from_records(
            cls, records: tuple[RoutingTelemetryRecord, ...]) -> "LocalTelemetrySnapshot":
        counts: dict[str, int] = {}
        for record in records:
            counts[record.requested_model] = counts.get(record.requested_model, 0) + 1
        sample_total = len(records)
        confidence = "meaningful" if sample_total >= 30 else (
            "informative" if sample_total >= 10 else "unknown"
        )
        return cls(counts, confidence, records)


@dataclass(frozen=True)
class ModelCandidate:
    runtime: RuntimeModel
    effort: str
    benchmark: BenchmarkModel | None
    binding_confidence: str = "unknown"

    @property
    def quality_score(self) -> float | None:
        return self.benchmark.coding_index if self.benchmark else None

    @property
    def expected_wall_ms(self) -> int | None:
        return self.benchmark.expected_wall_ms if self.benchmark else None

    @property
    def expected_cost_usd(self) -> float | None:
        return self.benchmark.cost_per_task_usd if self.benchmark else None


@dataclass(frozen=True)
class ModelCatalog:
    provider_catalog: ProviderCatalog
    benchmark_catalog: BenchmarkCatalog
    bindings: tuple[ModelBenchmarkBinding, ...] = ()
    local_telemetry: LocalTelemetrySnapshot = LocalTelemetrySnapshot()

    def candidates(self) -> tuple[ModelCandidate, ...]:
        benchmark_by_id = {
            item.benchmark_model_id: item for item in self.benchmark_catalog.models
        }
        binding_by_runtime_effort = {
            (item.runtime_model_id, item.effort): item for item in self.bindings
        }
        result: list[ModelCandidate] = []
        for runtime in self.provider_catalog.models:
            for effort in runtime.effort_levels:
                binding = binding_by_runtime_effort.get((runtime.runtime_model_id, effort))
                benchmark = (
                    benchmark_by_id.get(binding.benchmark_model_id) if binding else None
                )
                result.append(ModelCandidate(
                    runtime, effort, benchmark,
                    binding.confidence if binding else "unknown",
                ))
        return tuple(result)


def default_model_catalog(
        availability: Mapping[str, Availability] | None = None) -> ModelCatalog:
    """Build the pinned PR7 catalog; availability must come from discovery."""

    known = availability or {}
    runtimes = (
        RuntimeModel(
            "openai", "codex", "gpt-5.6-luna", "luna", ("medium", "high"),
            known.get("gpt-5.6-luna", Availability.UNKNOWN), ApprovalClass.NORMAL,
            ("coding", "research", "design"),
        ),
        RuntimeModel(
            "openai", "codex", "gpt-5.6-terra", "terra",
            ("medium", "high", "xhigh"),
            known.get("gpt-5.6-terra", Availability.UNKNOWN), ApprovalClass.NORMAL,
            ("coding", "design", "verification"),
        ),
        RuntimeModel(
            "openai", "codex", "gpt-5.6-sol", "sol",
            ("medium", "high", "xhigh"),
            known.get("gpt-5.6-sol", Availability.UNKNOWN), ApprovalClass.PREMIUM,
            ("coding", "design", "verification"),
        ),
        RuntimeModel(
            "anthropic", "claude", "claude-sonnet-5", "sonnet",
            ("medium", "high"),
            known.get("claude-sonnet-5", Availability.UNKNOWN), ApprovalClass.NORMAL,
            ("coding", "research", "design", "verification"),
        ),
        RuntimeModel(
            "anthropic", "claude", "claude-opus-5", "opus",
            ("medium", "high", "xhigh"),
            known.get("claude-opus-5", Availability.UNKNOWN), ApprovalClass.PREMIUM,
            ("design", "verification"),
        ),
    )
    snapshot = load_benchmark_snapshot()
    explicit_runtime_ids = {
        "luna": "gpt-5.6-luna", "terra": "gpt-5.6-terra",
        "sol": "gpt-5.6-sol", "opus": "claude-opus-5",
    }
    bindings = tuple(
        ModelBenchmarkBinding(
            benchmark.benchmark_model_id,
            explicit_runtime_ids[benchmark.family], benchmark.effort,
            benchmark.benchmark_confidence,
        )
        for benchmark in snapshot.models
        if benchmark.family in explicit_runtime_ids
    )
    return ModelCatalog(ProviderCatalog(runtimes), snapshot, bindings)


@dataclass(frozen=True)
class TaskFeatures:
    node_id: str
    team: str
    role: str
    risk: str
    uncertainty: int
    scope: int
    synthesis: int
    task_kind: str
    read_only: bool
    write_required: bool
    estimated_context: int = 0
    expected_output: str = ""
    latency_priority: str = "high"
    requires_cross_provider: bool = False
    requires_independent_verifier: bool = False
    excluded_provider: str = ""
    tool_requirements: tuple[str, ...] = ()
    adapter_requirements: tuple[str, ...] = ()
    previous_failure_reason: str = ""
    permission_profile: str = "workspace_write"
    preferred_runtime_model_id: str = ""

    @classmethod
    def from_node(cls, node: Any) -> "TaskFeatures":
        scope = len(set((*node.read_scope, *node.write_scope)))
        explicit = getattr(node, "task_kind", "")
        if explicit:
            task_kind = explicit
        elif node.kind == "verifier" or node.team_id == "verification":
            task_kind = "verification"
        elif node.team_id == "research":
            task_kind = "research"
        elif node.team_id == "design":
            task_kind = (
                "critical_synthesis"
                if node.risk == "critical" or getattr(node, "synthesis", 0) >= 3
                else "design"
            )
        elif node.team_id == "implementation":
            if node.risk == "critical" and getattr(node, "synthesis", 0) >= 2:
                task_kind = "critical_synthesis"
            elif node.risk == "high" or node.uncertainty >= 3 or scope >= 5:
                task_kind = "complex_implementation"
            elif node.risk == "medium" or node.uncertainty >= 2 or scope >= 3:
                task_kind = "general_implementation"
            else:
                task_kind = "bounded_implementation"
        else:
            task_kind = "deterministic" if not node.write_scope else "routine"
        return cls(
            node.node_id, node.team_id, node.role, node.risk, node.uncertainty,
            scope, getattr(node, "synthesis", 0), task_kind,
            not node.write_scope, bool(node.write_scope),
            estimated_context=node.estimated_context_tokens,
            expected_output=node.title,
            requires_cross_provider=getattr(node, "requires_cross_provider", False),
            requires_independent_verifier=(node.verification_policy == "independent"),
            excluded_provider=getattr(node, "excluded_provider", ""),
            tool_requirements=tuple(node.skills),
            adapter_requirements=tuple(getattr(node, "adapter_requirements", ())),
            permission_profile=getattr(node, "permission_profile", "workspace_write"),
        )


@dataclass(frozen=True)
class RouteTarget:
    provider: str
    adapter: str
    runtime_model_id: str
    family: str
    effort: str
    approval_class: ApprovalClass
    quality_score: float | None = None
    expected_wall_ms: int | None = None
    expected_cost_usd: float | None = None

    @classmethod
    def no_model(cls) -> "RouteTarget":
        return cls("", "", "", "", "", ApprovalClass.NORMAL)

    @classmethod
    def from_candidate(cls, candidate: ModelCandidate) -> "RouteTarget":
        runtime = candidate.runtime
        return cls(
            runtime.provider, runtime.adapter, runtime.runtime_model_id,
            runtime.family, candidate.effort, runtime.approval_class,
            candidate.quality_score, candidate.expected_wall_ms,
            candidate.expected_cost_usd,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RouteTarget":
        data = dict(value)
        data["approval_class"] = ApprovalClass(data["approval_class"])
        return cls(**data)


@dataclass(frozen=True)
class PremiumApprovalEnvelope:
    node_id: str
    provider_family: str
    model_family: str
    max_effort: str
    write_scope_digest: str
    permission_profile: str
    run_id: str
    plan_version: int

    @staticmethod
    def scope_digest(write_scope: tuple[str, ...]) -> str:
        encoded = json.dumps(
            sorted(set(write_scope)), separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    @classmethod
    def for_node(cls, run_id: str, plan_version: int, node: Any) -> "PremiumApprovalEnvelope":
        return cls(
            node.node_id,
            getattr(node, "provider_family", ""),
            getattr(node, "model_family", ""),
            node.effort,
            cls.scope_digest(tuple(node.write_scope)),
            getattr(node, "permission_profile", "workspace_write"),
            run_id,
            plan_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PremiumApprovalEnvelope":
        return cls(**value)

    def covers(self, run_id: str, plan_version: int,
               node: Any, target: RouteTarget) -> bool:
        return all((
            self.run_id == run_id,
            self.plan_version <= plan_version,
            self.node_id == node.node_id,
            self.provider_family == target.provider,
            self.model_family == target.family,
            _EFFORT_ORDER.get(target.effort, 10**6)
            <= _EFFORT_ORDER.get(self.max_effort, -1),
            self.write_scope_digest == self.scope_digest(tuple(node.write_scope)),
            self.permission_profile
            == getattr(node, "permission_profile", "workspace_write"),
        ))


@dataclass(frozen=True)
class RoutingDecision:
    node_id: str
    primary: RouteTarget
    fallbacks: tuple[RouteTarget, ...]
    reason_codes: tuple[str, ...]
    benchmark_snapshot_id: str
    benchmark_confidence: str
    routing_mode: RoutingMode
    local_samples: int = 0
    decision_digest: str = ""

    def __post_init__(self) -> None:
        body = self.to_dict(include_digest=False)
        encoded = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.decision_digest and self.decision_digest != expected:
            raise ValueError("routing decision digest mismatch")
        object.__setattr__(self, "decision_digest", expected)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        def target(value: RouteTarget) -> dict[str, Any]:
            result = asdict(value)
            result["approval_class"] = value.approval_class.value
            return result

        result = {
            "node_id": self.node_id,
            "primary": target(self.primary),
            "fallbacks": [target(item) for item in self.fallbacks],
            "reason_codes": list(self.reason_codes),
            "benchmark_snapshot_id": self.benchmark_snapshot_id,
            "benchmark_confidence": self.benchmark_confidence,
            "routing_mode": self.routing_mode.value,
            "local_samples": self.local_samples,
        }
        if include_digest:
            result["decision_digest"] = self.decision_digest
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RoutingDecision":
        data = dict(value)
        data["primary"] = RouteTarget.from_dict(data["primary"])
        data["fallbacks"] = tuple(
            RouteTarget.from_dict(item) for item in data.get("fallbacks", ())
        )
        data["reason_codes"] = tuple(data.get("reason_codes", ()))
        data["routing_mode"] = RoutingMode(data["routing_mode"])
        return cls(**data)


_QUALITY_FLOORS = {
    "routine": 42.0,
    "bounded_implementation": 48.0,
    "general_implementation": 56.0,
    "complex_implementation": 56.0,
    "design": 56.0,
    "verification": 56.0,
    "critical_synthesis": 64.0,
}

_CAPABILITIES = {
    "routine": ("research", "coding"),
    "research": ("research",),
    "bounded_implementation": ("coding",),
    "general_implementation": ("coding",),
    "complex_implementation": ("coding",),
    "design": ("design",),
    "verification": ("verification",),
    "critical_synthesis": ("design",),
}

_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}


class ModelRouter:
    """Select the fastest candidate that satisfies an explicit quality floor."""

    def __init__(self, catalog: ModelCatalog,
                 *, mode: RoutingMode = RoutingMode.BALANCED) -> None:
        self.catalog = catalog
        self.mode = mode

    @staticmethod
    def _latency_key(candidate: ModelCandidate) -> tuple[Any, ...]:
        return (
            candidate.expected_wall_ms is None,
            candidate.expected_wall_ms or 10**12,
            candidate.expected_cost_usd is None,
            candidate.expected_cost_usd or 10**12,
            -(candidate.runtime.reliability_prior or 0.0),
            candidate.runtime.provider,
            candidate.runtime.runtime_model_id,
            _EFFORT_ORDER.get(candidate.effort, 99),
        )

    @staticmethod
    def _fallback_key(candidate: ModelCandidate) -> tuple[Any, ...]:
        return (
            -(candidate.quality_score if candidate.quality_score is not None else -1.0),
            candidate.expected_wall_ms is None,
            candidate.expected_wall_ms or 10**12,
            candidate.runtime.provider,
            candidate.runtime.runtime_model_id,
            _EFFORT_ORDER.get(candidate.effort, 99),
        )

    def route(self, features: TaskFeatures) -> RoutingDecision:
        if features.task_kind == "deterministic":
            return RoutingDecision(
                features.node_id, RouteTarget.no_model(), (),
                ("DETERMINISTIC_NO_MODEL",),
                self.catalog.benchmark_catalog.snapshot_digest,
                "not_applicable", self.mode,
            )

        capabilities = _CAPABILITIES.get(features.task_kind)
        if capabilities is None:
            raise ValueError(f"unsupported task kind: {features.task_kind}")
        floor = _QUALITY_FLOORS.get(features.task_kind, 0.0)
        if self.mode is RoutingMode.QUALITY and features.task_kind != "critical_synthesis":
            floor += self.catalog.benchmark_catalog.quality_equivalence_margin

        all_capable = [
            item for item in self.catalog.candidates()
            if any(capability in item.runtime.capabilities for capability in capabilities)
            and (not features.adapter_requirements
                 or item.runtime.adapter in features.adapter_requirements)
            and (not features.requires_cross_provider
                 or item.runtime.provider != features.excluded_provider)
        ]
        available = [
            item for item in all_capable
            if item.runtime.availability is Availability.AVAILABLE
        ]
        if not available:
            raise LookupError("no available model satisfies adapter/provider constraints")

        benchmark_qualified = [
            item for item in available
            if item.quality_score is not None and item.quality_score >= floor
        ]
        allow_partial = features.task_kind in {"research", "design", "verification"}
        partial = [item for item in available if item.quality_score is None]
        # A discovered provider-only environment remains usable without
        # inventing a benchmark score. Coding accepts partial evidence only
        # when no scored candidate is available; known candidates always keep
        # the explicit quality-floor contract.
        qualified = benchmark_qualified + (partial if allow_partial else [])
        if not qualified and partial:
            qualified = partial
        if not qualified:
            raise LookupError("no available model meets the quality floor")

        normal = [
            item for item in qualified
            if item.runtime.approval_class is ApprovalClass.NORMAL
        ]
        pool = normal or qualified
        primary = min(pool, key=self._latency_key)
        reasons = [features.task_kind.upper()]
        reasons.append(
            "BENCHMARK_PARTIAL_PROVIDER_ONLY"
            if primary.quality_score is None else "QUALITY_FLOOR_MET"
        )
        reasons.append("LATENCY_FIRST")
        unavailable_better = [
            item for item in all_capable
            if item.runtime.availability is Availability.UNAVAILABLE
            and item.quality_score is not None and item.quality_score >= floor
            and self._latency_key(item) < self._latency_key(primary)
        ]
        if unavailable_better:
            reasons.append("PRIMARY_UNAVAILABLE_FALLBACK")
        if primary.runtime.approval_class is ApprovalClass.PREMIUM:
            reasons.append("PREMIUM_QUALITY_FLOOR_REQUIRED")
        preferred = next((
            item for item in pool
            if item.runtime.runtime_model_id == features.preferred_runtime_model_id
        ), None)
        if (preferred is not None and preferred.expected_wall_ms is not None
                and primary.expected_wall_ms is not None
                and primary.expected_wall_ms > preferred.expected_wall_ms * 0.9):
            primary = preferred
            reasons.append("CURRENT_ROUTE_WITHIN_HYSTERESIS")

        remaining = [item for item in qualified if item != primary]
        if primary.runtime.approval_class is ApprovalClass.PREMIUM:
            nonpremium = [
                item for item in available
                if item.runtime.approval_class is ApprovalClass.NORMAL
                and any(capability in item.runtime.capabilities
                        for capability in capabilities)
            ]
            remaining = sorted(nonpremium, key=self._fallback_key) + remaining
        deduplicated: list[ModelCandidate] = []
        seen: set[tuple[str, str]] = set()
        for item in remaining:
            identity = (item.runtime.runtime_model_id, item.effort)
            if identity not in seen:
                seen.add(identity)
                deduplicated.append(item)

        confidence = (
            "partial" if primary.benchmark is None else primary.binding_confidence
        )
        local_samples = int(
            self.catalog.local_telemetry.sample_counts.get(
                primary.runtime.runtime_model_id, 0,
            )
        )
        return RoutingDecision(
            features.node_id, RouteTarget.from_candidate(primary),
            tuple(RouteTarget.from_candidate(item) for item in deduplicated),
            tuple(reasons), self.catalog.benchmark_catalog.snapshot_digest,
            confidence, self.mode, local_samples,
        )

    def route_plan(self, plan: Any) -> Any:
        decisions = tuple(
            self.route(TaskFeatures.from_node(node)) for node in plan.nodes
        )
        by_node = {item.node_id: item for item in decisions}
        routed = []
        for node in plan.nodes:
            decision = by_node[node.node_id]
            primary = decision.primary
            fallback = decision.fallbacks[0] if decision.fallbacks else RouteTarget.no_model()
            routed.append(replace(
                node,
                provider=primary.adapter,
                provider_family=primary.provider,
                adapter=primary.adapter,
                model=primary.runtime_model_id,
                model_family=primary.family,
                effort=primary.effort,
                fallback_provider_family=fallback.provider,
                fallback_adapter=fallback.adapter,
                fallback_model=fallback.runtime_model_id,
                fallback_model_family=fallback.family,
                fallback_effort=fallback.effort,
                fallback_approval_class=fallback.approval_class.value,
                approval_required=(primary.approval_class is ApprovalClass.PREMIUM),
                approval_class=primary.approval_class.value,
                routing_reason_codes=decision.reason_codes,
                routing_decision_digest=decision.decision_digest,
                routing_confidence=decision.benchmark_confidence,
            ))
        return replace(
            plan, nodes=tuple(routed), routing_decisions=decisions,
            benchmark_snapshot_id=self.catalog.benchmark_catalog.snapshot_digest,
        )
