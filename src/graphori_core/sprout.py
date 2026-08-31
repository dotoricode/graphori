"""Proof-driven graph growth for Graphori Sprout.

The module is deliberately runtime-independent.  It decides which proof may
unlock expansion, fan-in, or commit; adapters remain responsible only for
executing the resulting nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
from itertools import combinations
import json
from typing import Iterable

from .run_plan import NodeSpec, RunPlan


class TransitionAuthority(str, Enum):
    EXPAND = "expand"
    FAN_IN = "fan_in"
    COMMIT = "commit"


class ProofState(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class GrowthAction(str, Enum):
    SPAWN = "spawn"
    USE_STATIC = "use_static"
    STOP = "stop"
    RETRY = "retry"
    ESCALATE = "escalate"


class SproutRoute(str, Enum):
    V2 = "v2"
    SPROUT = "sprout"


@dataclass(frozen=True)
class ProofObligation:
    obligation_id: str
    verifier: str

    def __post_init__(self) -> None:
        if not self.obligation_id.strip() or not self.verifier.strip():
            raise ValueError("proof obligation ID and verifier must be non-empty")


@dataclass(frozen=True)
class ProofResult:
    obligation_id: str
    state: ProofState | str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.obligation_id.strip():
            raise ValueError("invalid proof result")
        try:
            object.__setattr__(self, "state", ProofState(self.state))
        except ValueError as exc:
            raise ValueError("invalid proof result") from exc
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))
        if self.state != "unknown" and not self.evidence_refs:
            raise ValueError("a decided proof requires evidence")


@dataclass(frozen=True)
class ProofCarryingArtifact:
    artifact_id: str
    payload_ref: str
    lineage: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    journal_ref: str = ""
    obligations: tuple[ProofObligation, ...] = ()
    results: tuple[ProofResult, ...] = ()

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.payload_ref.strip():
            raise ValueError("artifact ID and payload reference must be non-empty")
        obligations = tuple(sorted(self.obligations, key=lambda item: item.obligation_id))
        results = tuple(sorted(self.results, key=lambda item: item.obligation_id))
        obligation_ids = [item.obligation_id for item in obligations]
        result_ids = [item.obligation_id for item in results]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("duplicate proof obligation")
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("duplicate proof result")
        undeclared = set(result_ids) - set(obligation_ids)
        if undeclared:
            raise ValueError(f"undeclared proof result: {sorted(undeclared)}")
        object.__setattr__(self, "lineage", tuple(dict.fromkeys(self.lineage)))
        object.__setattr__(self, "claims", tuple(sorted(set(self.claims))))
        object.__setattr__(self, "obligations", obligations)
        object.__setattr__(self, "results", results)

    @property
    def result_states(self) -> dict[str, ProofState]:
        return {item.obligation_id: item.state for item in self.results}

    @property
    def open_obligations(self) -> tuple[str, ...]:
        decided = set(self.result_states)
        return tuple(item.obligation_id for item in self.obligations
                     if item.obligation_id not in decided)

    @property
    def failed_obligations(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, state in self.result_states.items()
                            if state is ProofState.FAILED))

    @property
    def unknown_obligations(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, state in self.result_states.items()
                            if state is ProofState.UNKNOWN))

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return tuple(sorted({reference for result in self.results
                             for reference in result.evidence_refs}))

    @property
    def qualified(self) -> bool:
        return bool(self.obligations) and not (
            self.open_obligations or self.failed_obligations or self.unknown_obligations
        )

    def canonical_json(self) -> str:
        return json.dumps({
            "artifact_id": self.artifact_id,
            "claims": list(self.claims),
            "journal_ref": self.journal_ref,
            "lineage": list(self.lineage),
            "obligations": [
                {"obligation_id": item.obligation_id, "verifier": item.verifier}
                for item in self.obligations
            ],
            "payload_ref": self.payload_ref,
            "results": [
                {"evidence_refs": list(item.evidence_refs),
                 "obligation_id": item.obligation_id, "state": item.state.value}
                for item in self.results
            ],
        }, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class GrowthCandidate:
    node: NodeSpec
    closes_obligations: tuple[str, ...]

    def __post_init__(self) -> None:
        obligations = tuple(sorted(set(self.closes_obligations)))
        if not obligations:
            raise ValueError("growth candidate must close at least one proof obligation")
        if obligations != tuple(sorted(set(self.node.closes_proofs))):
            raise ValueError("candidate proofs must match node closes_proofs")
        object.__setattr__(self, "closes_obligations", obligations)


@dataclass(frozen=True)
class AuthorityDecision:
    authority: TransitionAuthority
    granted: bool
    reason: str
    proof_refs: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    scope_digest: str = ""
    policy_version: str = ""


@dataclass(frozen=True)
class GrowthDecision:
    action: GrowthAction | str
    target_node_ids: tuple[str, ...] = ()
    target_obligations: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    policy_version: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "action", GrowthAction(self.action))
        except ValueError as exc:
            raise ValueError("invalid growth action") from exc

    def canonical_json(self) -> str:
        return json.dumps({
            "action": self.action.value,
            "policy_version": self.policy_version,
            "proof_refs": list(self.proof_refs),
            "reason": self.reason,
            "target_node_ids": list(self.target_node_ids),
            "target_obligations": list(self.target_obligations),
        }, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class SproutShadowTelemetry:
    """Immutable planning evidence; callers may journal it but it is not truth."""

    actual_route: SproutRoute | str
    target_count: int
    targets_independent: bool | None
    uncertain: bool
    conditional_enabled: bool
    activation_eligible: bool
    activation_reason: str
    v2_node_ids: tuple[str, ...]
    shadow_node_ids: tuple[str, ...]
    required_proofs: tuple[str, ...]
    v2_proofs_closed: tuple[str, ...]
    shadow_proofs_closed: tuple[str, ...]
    estimated_v2_latency_ms: int
    estimated_shadow_latency_ms: int | None
    estimated_gain_ms: int | None
    estimated_gain_basis_points: int | None
    planning_cost_ms: int
    v2_ai_nodes: int
    shadow_ai_nodes: int | None
    incorrect_expansion: bool
    missed_expansion: bool

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "actual_route", SproutRoute(self.actual_route))
        except ValueError as exc:
            raise ValueError("invalid Sprout actual route") from exc
        if self.target_count < 1 or self.planning_cost_ms < 0:
            raise ValueError("invalid Sprout telemetry inputs")
        for name in (
            "v2_node_ids", "shadow_node_ids", "required_proofs",
            "v2_proofs_closed", "shadow_proofs_closed",
        ):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))

    @property
    def proof_coverage_delta(self) -> int:
        if self.actual_route is SproutRoute.V2:
            return 0
        return self.shadow_proof_coverage_delta

    @property
    def shadow_proof_coverage_delta(self) -> int:
        return len(self.shadow_proofs_closed) - len(self.v2_proofs_closed)

    def canonical_json(self) -> str:
        return json.dumps({
            "activation_eligible": self.activation_eligible,
            "activation_reason": self.activation_reason,
            "actual_route": self.actual_route.value,
            "conditional_enabled": self.conditional_enabled,
            "estimated_gain_basis_points": self.estimated_gain_basis_points,
            "estimated_gain_ms": self.estimated_gain_ms,
            "estimated_shadow_latency_ms": self.estimated_shadow_latency_ms,
            "estimated_v2_latency_ms": self.estimated_v2_latency_ms,
            "incorrect_expansion": self.incorrect_expansion,
            "missed_expansion": self.missed_expansion,
            "planning_cost_ms": self.planning_cost_ms,
            "shadow_ai_nodes": self.shadow_ai_nodes,
            "required_proofs": list(self.required_proofs),
            "shadow_node_ids": list(self.shadow_node_ids),
            "shadow_proofs_closed": list(self.shadow_proofs_closed),
            "target_count": self.target_count,
            "targets_independent": self.targets_independent,
            "uncertain": self.uncertain,
            "v2_node_ids": list(self.v2_node_ids),
            "v2_ai_nodes": self.v2_ai_nodes,
            "v2_proofs_closed": list(self.v2_proofs_closed),
        }, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class SproutPlanningResult:
    actual: GrowthDecision
    shadow: GrowthDecision
    telemetry: SproutShadowTelemetry


class ProofFrontier:
    """Evaluate bounded proof-driven planning decisions deterministically."""

    def __init__(self, *, policy_version: str, max_candidates: int = 32,
                 max_branch_budget: int = 4):
        if not policy_version.strip():
            raise ValueError("policy version must be non-empty")
        if max_candidates < 1 or max_branch_budget < 1:
            raise ValueError("proof search limits must be positive")
        self.policy_version = policy_version
        self.max_candidates = max_candidates
        self.max_branch_budget = max_branch_budget

    def authorize(
        self,
        authority: TransitionAuthority | str,
        artifacts: tuple[ProofCarryingArtifact, ...],
        *,
        irreversible: bool = False,
        human_proof: str = "",
        scope_digest: str = "",
        trusted_artifact_digests: frozenset[str] = frozenset(),
    ) -> AuthorityDecision:
        try:
            authority = TransitionAuthority(authority)
        except ValueError as exc:
            raise ValueError("invalid transition authority") from exc
        if not scope_digest:
            raise ValueError("authority scope digest must be non-empty")
        if not artifacts:
            return AuthorityDecision(authority, False, "missing_artifact",
                                     scope_digest=scope_digest,
                                     policy_version=self.policy_version)
        if len({item.artifact_id for item in artifacts}) != len(artifacts):
            return AuthorityDecision(authority, False, "duplicate_artifact",
                                     scope_digest=scope_digest,
                                     policy_version=self.policy_version)
        artifact_digests = tuple(sorted(item.digest() for item in artifacts))
        if any(not item.journal_ref for item in artifacts):
            return AuthorityDecision(authority, False, "unpersisted_artifact",
                                     scope_digest=scope_digest,
                                     policy_version=self.policy_version)
        if not set(artifact_digests) <= trusted_artifact_digests:
            return AuthorityDecision(
                authority, False, "artifact_not_trusted",
                artifact_digests=artifact_digests, scope_digest=scope_digest,
                policy_version=self.policy_version,
            )
        if any(not item.claims for item in artifacts):
            return AuthorityDecision(
                authority, False, "missing_claim", artifact_digests=artifact_digests,
                scope_digest=scope_digest, policy_version=self.policy_version,
            )
        if any(item.failed_obligations for item in artifacts):
            reason = "failed_proof"
        elif any(item.unknown_obligations for item in artifacts):
            reason = "unknown_proof"
        elif any(item.open_obligations or not item.qualified for item in artifacts):
            reason = "open_proof"
        elif authority is TransitionAuthority.COMMIT and irreversible:
            reason = "runtime_human_gate_required"
        else:
            proof_refs = {reference for item in artifacts for reference in item.evidence_refs}
            if human_proof and not irreversible:
                proof_refs.add(human_proof)
            return AuthorityDecision(
                authority, True, "proofs_closed", tuple(sorted(proof_refs)),
                artifact_digests, scope_digest,
                self.policy_version,
            )
        return AuthorityDecision(authority, False, reason,
                                 artifact_digests=tuple(sorted(
                                     item.digest() for item in artifacts
                                 )), scope_digest=scope_digest,
                                 policy_version=self.policy_version)

    @staticmethod
    def _wave_latency(nodes: tuple[NodeSpec, ...], repetitions: int,
                      max_wip: int) -> int:
        lanes = [0] * max_wip
        costs = sorted(
            (node.estimated_startup_ms + node.estimated_execution_ms
             for node in nodes for _ in range(repetitions)),
            reverse=True,
        )
        for cost in costs:
            lane = min(range(max_wip), key=lambda index: (lanes[index], index))
            lanes[lane] += cost
        return max(lanes, default=0)

    def route_if_profitable(
        self,
        artifact: ProofCarryingArtifact,
        candidates: tuple[GrowthCandidate, ...],
        static_nodes: tuple[NodeSpec, ...],
        *,
        target_count: int,
        branch_budget: int = 2,
        max_wip: int = 2,
        min_gain_ms: int = 30_000,
        min_gain_ratio: float = 0.15,
        coordination_overhead_ms: int = 0,
    ) -> GrowthDecision:
        """Use a pilot only when declared estimates beat the existing static route."""
        if (target_count < 1 or max_wip < 1 or min_gain_ms < 0
                or min_gain_ratio < 0 or coordination_overhead_ms < 0):
            raise ValueError("invalid routing performance inputs")
        decision = self.route(
            artifact, candidates, branch_budget=branch_budget, max_wip=max_wip,
        )
        if decision.action is not GrowthAction.SPAWN:
            static_proofs = {
                proof for node in static_nodes for proof in node.closes_proofs
            }
            if (decision.reason in {
                    "no_candidate_cover", "search_budget_exceeded",
                    "candidate_input_exceeded",
                } and set(decision.target_obligations) <= static_proofs):
                return GrowthDecision(
                    "use_static", tuple(sorted(node.node_id for node in static_nodes)),
                    decision.target_obligations, artifact.evidence_refs,
                    self.policy_version, "pilot_schedule_uncertain",
                )
            return decision
        targets = set(decision.target_obligations)
        if not targets <= {proof for node in static_nodes for proof in node.closes_proofs}:
            return GrowthDecision(
                "escalate", target_obligations=decision.target_obligations,
                policy_version=self.policy_version, reason="static_route_incomplete",
            )
        selected_ids = set(decision.target_node_ids)
        selected = tuple(item.node for item in candidates
                         if item.node.node_id in selected_ids)
        if (target_count > 1 and any(node.write_scope for node in selected)) or any(
            node.dependencies for node in selected
        ) or any(
            self._scope_conflict(left, right)
            for index, left in enumerate(selected)
            for right in selected[index + 1:]
        ):
            return GrowthDecision(
                "use_static", tuple(sorted(node.node_id for node in static_nodes)),
                decision.target_obligations, artifact.evidence_refs,
                self.policy_version, "pilot_schedule_uncertain",
            )
        static_latency = self._wave_latency(static_nodes, target_count, max_wip)
        sparse_latency = (
            self._wave_latency(selected, 1, max_wip)
            + self._wave_latency(selected, target_count, max_wip)
            + coordination_overhead_ms
        )
        threshold = max(min_gain_ms, int(static_latency * min_gain_ratio))
        if static_latency - sparse_latency <= threshold:
            return GrowthDecision(
                "use_static", tuple(sorted(node.node_id for node in static_nodes)),
                decision.target_obligations, artifact.evidence_refs,
                self.policy_version, "pilot_not_profitable",
            )
        return decision

    def _plan_with_shadow(
        self,
        artifact: ProofCarryingArtifact,
        candidates: tuple[GrowthCandidate, ...],
        static_nodes: tuple[NodeSpec, ...],
        *,
        target_count: int,
        targets_independent: bool | None,
        uncertain: bool,
        conditional_enabled: bool,
        branch_budget: int = 2,
        max_wip: int = 2,
        min_gain_ms: int = 30_000,
        min_gain_ratio: float = 0.15,
        coordination_overhead_ms: int = 0,
    ) -> SproutPlanningResult:
        """Plan Sprout beside v2 and activate only a fully proven opt-in case."""
        if (target_count < 1 or max_wip < 1 or min_gain_ms < 0
                or min_gain_ratio < 0 or coordination_overhead_ms < 0):
            raise ValueError("invalid shadow-planning inputs")
        required = artifact.failed_obligations or artifact.open_obligations
        static_ids = tuple(sorted(node.node_id for node in static_nodes))
        static_proofs = tuple(sorted({
            proof for node in static_nodes for proof in node.closes_proofs
            if proof in set(required)
        }))
        static_latency = self._wave_latency(static_nodes, target_count, max_wip)
        shadow = self.route(
            artifact, candidates, branch_budget=branch_budget, max_wip=max_wip,
        )
        selected_ids = (
            set(shadow.target_node_ids)
            if shadow.action is GrowthAction.SPAWN else set()
        )
        selected = tuple(
            item.node for item in candidates if item.node.node_id in selected_ids
        )
        shadow_proofs = tuple(sorted({
            proof for node in selected for proof in node.closes_proofs
            if proof in set(required)
        }))
        schedule_safe = bool(selected) and not (
            any(node.dependencies for node in selected)
            or any(node.write_scope for node in selected)
            or any(
                self._scope_conflict(left, right)
                for index, left in enumerate(selected)
                for right in selected[index + 1:]
            )
        )
        shadow_latency = None
        gain_ms = None
        gain_basis_points = None
        v2_ai_nodes = sum(
            node.provider != "generic-process" for node in static_nodes
        ) * target_count
        shadow_ai_nodes = None
        if shadow.action is GrowthAction.SPAWN and schedule_safe:
            shadow_latency = (
                self._wave_latency(selected, 1, max_wip)
                + self._wave_latency(selected, target_count, max_wip)
                + coordination_overhead_ms
            )
            gain_ms = static_latency - shadow_latency
            gain_basis_points = (
                gain_ms * 10_000 // static_latency if static_latency else 0
            )
            selected_ai = sum(
                node.provider != "generic-process" for node in selected
            )
            shadow_ai_nodes = selected_ai * (target_count + 1)

        required_set = set(required)
        coverage_safe = (
            required_set <= set(static_proofs)
            and set(static_proofs) <= set(shadow_proofs)
        )
        threshold = max(min_gain_ms, int(static_latency * min_gain_ratio))
        if uncertain or targets_independent is None:
            eligible, reason = False, "planning_uncertain"
        elif target_count < 4:
            eligible, reason = False, "target_count_below_four"
        elif not targets_independent:
            eligible, reason = False, "targets_not_independent"
        elif shadow.action is not GrowthAction.SPAWN:
            eligible, reason = False, shadow.reason
        elif not schedule_safe:
            eligible, reason = False, "pilot_schedule_uncertain"
        elif not coverage_safe:
            eligible, reason = False, "proof_coverage_reduced"
        elif shadow_ai_nodes is None or shadow_ai_nodes > v2_ai_nodes:
            eligible, reason = False, "ai_session_count_increased"
        elif gain_ms is None or gain_ms <= threshold:
            eligible, reason = False, "pilot_not_profitable"
        else:
            eligible = True
            reason = "conditional_sprout_eligible"

        activated = conditional_enabled and eligible
        actual = shadow if activated else GrowthDecision(
            "use_static", static_ids, tuple(sorted(required)), artifact.evidence_refs,
            self.policy_version,
            "conditional_sprout_activated" if activated else (
                "shadow_only" if eligible else reason
            ),
        )
        actual_route = SproutRoute.SPROUT if activated else SproutRoute.V2
        telemetry = SproutShadowTelemetry(
            actual_route=actual_route,
            target_count=target_count,
            targets_independent=targets_independent,
            uncertain=uncertain,
            conditional_enabled=conditional_enabled,
            activation_eligible=eligible,
            activation_reason=("conditional_sprout_activated" if activated else reason),
            v2_node_ids=static_ids,
            shadow_node_ids=tuple(sorted(selected_ids)),
            required_proofs=tuple(sorted(required)),
            v2_proofs_closed=static_proofs,
            shadow_proofs_closed=shadow_proofs,
            estimated_v2_latency_ms=static_latency,
            estimated_shadow_latency_ms=shadow_latency,
            estimated_gain_ms=gain_ms,
            estimated_gain_basis_points=gain_basis_points,
            planning_cost_ms=coordination_overhead_ms,
            v2_ai_nodes=v2_ai_nodes,
            shadow_ai_nodes=shadow_ai_nodes,
            incorrect_expansion=activated and not eligible,
            missed_expansion=eligible and not activated,
        )
        return SproutPlanningResult(actual, shadow, telemetry)

    def plan_shadow(
        self,
        artifact: ProofCarryingArtifact,
        candidates: tuple[GrowthCandidate, ...],
        static_nodes: tuple[NodeSpec, ...],
        **kwargs,
    ) -> SproutPlanningResult:
        """Keep v2 actual while deterministically measuring a Sprout alternative."""
        return self._plan_with_shadow(
            artifact, candidates, static_nodes, conditional_enabled=False, **kwargs,
        )

    def plan_conditionally(
        self,
        artifact: ProofCarryingArtifact,
        candidates: tuple[GrowthCandidate, ...],
        static_nodes: tuple[NodeSpec, ...],
        **kwargs,
    ) -> SproutPlanningResult:
        """Opt in to Sprout only after every conservative activation gate passes."""
        return self._plan_with_shadow(
            artifact, candidates, static_nodes, conditional_enabled=True, **kwargs,
        )

    @staticmethod
    def _scope_conflict(left: NodeSpec, right: NodeSpec) -> bool:
        def overlap(first: str, second: str) -> bool:
            a, b = first.rstrip("/"), second.rstrip("/")
            return a == b or a.startswith(b + "/") or b.startswith(a + "/")

        return (
            any(overlap(a, b) for a in left.write_scope for b in right.write_scope)
            or any(overlap(a, b) for a in left.write_scope for b in right.read_scope)
            or any(overlap(a, b) for a in left.read_scope for b in right.write_scope)
        )

    @staticmethod
    def _cover(
        obligations: Iterable[str],
        candidates: tuple[GrowthCandidate, ...],
        branch_budget: int,
        max_wip: int,
    ) -> tuple[GrowthCandidate, ...]:
        required = tuple(sorted(set(obligations)))
        proof_bits = {proof: 1 << index for index, proof in enumerate(required)}
        required_mask = (1 << len(proof_bits)) - 1
        ordered = tuple(sorted(candidates, key=lambda item: item.node.node_id))
        prepared = tuple((
            item,
            sum(proof_bits.get(proof, 0) for proof in item.closes_obligations),
            item.node.estimated_startup_ms + item.node.estimated_execution_ms,
        ) for item in ordered)
        best = None
        best_key = None
        for size in range(1, min(branch_budget, len(prepared)) + 1):
            for group in combinations(prepared, size):
                nodes = tuple(item.node for item, _mask, _cost in group)
                if any(node.dependencies for node in nodes) or any(
                    ProofFrontier._scope_conflict(left, right)
                    for index, left in enumerate(nodes)
                    for right in nodes[index + 1:]
                ):
                    continue
                covered = 0
                for _item, mask, _cost in group:
                    covered |= mask
                if covered != required_mask:
                    continue
                key = (
                    ProofFrontier._wave_latency(
                        nodes, 1, max_wip,
                    ),
                    sum(cost for _item, _mask, cost in group),
                    len(group),
                    tuple(item.node.node_id for item, _mask, _cost in group),
                )
                if best_key is None or key < best_key:
                    best = tuple(item for item, _mask, _cost in group)
                    best_key = key
        return best or ()

    @staticmethod
    def _relevant_candidates(
        targets: tuple[str, ...], candidates: tuple[GrowthCandidate, ...],
    ) -> tuple[GrowthCandidate, ...]:
        required = set(targets)
        relevant = tuple(item for item in candidates
                         if required.intersection(item.closes_obligations))
        result = []
        for candidate in relevant:
            candidate_cost = (candidate.node.estimated_startup_ms
                              + candidate.node.estimated_execution_ms)
            candidate_cover = required.intersection(candidate.closes_obligations)
            dominated = any(
                other is not candidate
                and candidate_cover <= required.intersection(other.closes_obligations)
                and (
                    candidate_cost > (other.node.estimated_startup_ms
                                      + other.node.estimated_execution_ms)
                    or (candidate_cost == (other.node.estimated_startup_ms
                                           + other.node.estimated_execution_ms)
                        and other.node.node_id < candidate.node.node_id)
                )
                for other in relevant
            )
            if not dominated:
                result.append(candidate)
        return tuple(result)

    def route(
        self,
        artifact: ProofCarryingArtifact,
        candidates: tuple[GrowthCandidate, ...],
        *,
        branch_budget: int = 2,
        max_wip: int | None = None,
    ) -> GrowthDecision:
        if branch_budget < 1:
            raise ValueError("branch budget must be positive")
        max_wip = branch_budget if max_wip is None else max_wip
        if max_wip < 1:
            raise ValueError("max_wip must be positive")
        if artifact.unknown_obligations:
            return GrowthDecision(
                "escalate", target_obligations=artifact.unknown_obligations,
                policy_version=self.policy_version, reason="unknown_proof",
            )
        targets = artifact.failed_obligations or artifact.open_obligations
        if not targets:
            return GrowthDecision("stop", proof_refs=artifact.evidence_refs,
                                  policy_version=self.policy_version,
                                  reason="proofs_closed")
        target_set = set(targets)
        relevant_count = sum(
            bool(target_set.intersection(item.closes_obligations)) for item in candidates
        )
        if relevant_count > self.max_candidates * 8:
            return GrowthDecision(
                "escalate", target_obligations=targets,
                policy_version=self.policy_version, reason="candidate_input_exceeded",
            )
        candidates = self._relevant_candidates(targets, candidates)
        if (len(candidates) > self.max_candidates
                or branch_budget > self.max_branch_budget):
            return GrowthDecision(
                "escalate", target_obligations=targets,
                policy_version=self.policy_version, reason="search_budget_exceeded",
            )
        selected = self._cover(targets, candidates, branch_budget, max_wip)
        if not selected:
            return GrowthDecision(
                "escalate", target_obligations=targets,
                policy_version=self.policy_version, reason="no_candidate_cover",
            )
        action = "retry" if artifact.failed_obligations else "spawn"
        return GrowthDecision(
            action,
            tuple(sorted(item.node.node_id for item in selected)),
            tuple(sorted(targets)),
            artifact.evidence_refs,
            self.policy_version,
            "lowest_latency_proof_cover",
        )

    def expand_plan(
        self,
        plan: RunPlan,
        nodes: tuple[NodeSpec, ...],
        artifacts: tuple[ProofCarryingArtifact, ...],
        *,
        trusted_artifact_digests: frozenset[str],
    ) -> RunPlan:
        if plan.proof_policy != self.policy_version:
            raise ValueError("plan proof policy does not match ProofFrontier")
        authority = self.authorize(
            TransitionAuthority.EXPAND, artifacts, scope_digest=plan.digest(),
            trusted_artifact_digests=trusted_artifact_digests,
        )
        if not authority.granted:
            raise ValueError("plan expansion requires granted EXPAND authority")
        if not nodes or any(not item.closes_proofs for item in nodes):
            raise ValueError("every expanded node must close a proof obligation")
        known = {item.node_id for item in plan.nodes}
        duplicate = known.intersection(item.node_id for item in nodes)
        if duplicate:
            raise ValueError(f"expanded nodes already exist: {sorted(duplicate)}")
        return replace(
            plan,
            plan_version=plan.plan_version + 1,
            nodes=tuple((*plan.nodes, *nodes)),
        )
