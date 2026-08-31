#!/usr/bin/env python3
"""Run the deterministic Sprout routing-model benchmark."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from graphori_core import (  # noqa: E402
    GrowthCandidate, NodeSpec, ProofCarryingArtifact, ProofFrontier, ProofObligation,
)


ARMS = (
    "v1-target-review", "graphori-v2", "sprout-unconditional",
    "graphori-sprout", "oracle-static",
)
BRANCH_COUNTS = (1, 2, 4, 8, 16)
SEED = 20260831


@dataclass(frozen=True)
class CandidateSpec:
    node_id: str
    closes: tuple[str, ...]
    cost_ms: int
    executor: str


@dataclass(frozen=True)
class Workload:
    workload_id: str
    obligations: tuple[str, ...]
    candidates: tuple[CandidateSpec, ...]
    review_ms: int
    branch_budget: int


def candidate(node_id: str, closes: tuple[str, ...], cost_ms: int,
              executor: str = "process") -> CandidateSpec:
    return CandidateSpec(node_id, closes, cost_ms, executor)


REGIONAL = Workload(
    "regional-collection",
    ("schema", "content", "scope", "freshness", "safety", "completeness"),
    (
        candidate("schema-check", ("schema",), 18),
        candidate("content-agent", ("content",), 115, "agent"),
        candidate("scope-check", ("scope",), 14),
        candidate("freshness-check", ("freshness",), 28),
        candidate("safety-agent", ("safety",), 125, "agent"),
        candidate("completeness-check", ("completeness",), 24),
        candidate("shape-pack", ("schema", "scope", "completeness"), 31),
        candidate("evidence-pack", ("content", "freshness"), 121, "agent"),
        candidate("risk-pack", ("freshness", "safety"), 132, "agent"),
        candidate("reasoning-pack", ("content", "safety"), 138, "agent"),
    ),
    review_ms=96,
    branch_budget=3,
)

REPOSITORY = Workload(
    "repository-audit",
    ("syntax", "tests", "scope", "secrets", "license"),
    (
        candidate("syntax-check", ("syntax",), 12),
        candidate("test-runner", ("tests",), 72),
        candidate("scope-diff", ("scope",), 19),
        candidate("secret-scan", ("secrets",), 44),
        candidate("license-review", ("license",), 104, "agent"),
        candidate("code-health", ("syntax", "tests"), 79),
        candidate("trust-scan", ("scope", "secrets"), 51),
        candidate("release-trust", ("secrets", "license"), 118, "agent"),
        candidate("repository-pack", ("syntax", "scope", "license"), 127, "agent"),
    ),
    review_ms=112,
    branch_budget=3,
)

RELEASE = Workload(
    "release-preflight",
    ("build", "unit", "integration", "sbom", "signature", "version", "changelog"),
    (
        candidate("build", ("build",), 86),
        candidate("unit", ("unit",), 94),
        candidate("integration", ("integration",), 142),
        candidate("sbom", ("sbom",), 36),
        candidate("signature", ("signature",), 33),
        candidate("version", ("version",), 11),
        candidate("changelog", ("changelog",), 81, "agent"),
        candidate("test-pack", ("unit", "integration"), 156),
        candidate("supply-chain", ("sbom", "signature"), 51),
        candidate("metadata-pack", ("version", "changelog"), 88, "agent"),
        candidate("binary-pack", ("build", "sbom", "signature"), 109),
        candidate("release-review", ("build", "version", "changelog"), 137, "agent"),
    ),
    review_ms=151,
    branch_budget=4,
)

API_IMPORT = Workload(
    "api-import",
    ("schema", "auth", "idempotency", "pagination"),
    (
        candidate("schema", ("schema",), 22),
        candidate("auth", ("auth",), 97, "agent"),
        candidate("idempotency", ("idempotency",), 49),
        candidate("pagination", ("pagination",), 63),
        candidate("request-contract", ("schema", "auth"), 108, "agent"),
        candidate("stream-contract", ("idempotency", "pagination"), 76),
        candidate("import-review", ("auth", "idempotency", "pagination"), 126, "agent"),
    ),
    review_ms=103,
    branch_budget=2,
)

MATRIX = (REGIONAL, REPOSITORY, RELEASE, API_IMPORT)


def node(spec: CandidateSpec, cost_ms: int) -> NodeSpec:
    return NodeSpec(
        spec.node_id, "verification", spec.node_id, spec.node_id, "verifier",
        provider="generic-process" if spec.executor == "process" else "codex",
        adapter="generic-process" if spec.executor == "process" else "codex",
        task_kind="deterministic" if spec.executor == "process" else "analysis",
        estimated_execution_ms=cost_ms,
        closes_proofs=spec.closes,
    )


def materialize(work: Workload, repetition: int) -> tuple[
        tuple[GrowthCandidate, ...], int, str]:
    """Create one paired fixture shared by every arm and branch count."""
    rng = random.Random(f"{SEED}:{work.workload_id}:{repetition}")
    candidates = tuple(
        GrowthCandidate(node(item, max(1, round(item.cost_ms * rng.uniform(0.9, 1.1)))),
                        item.closes)
        for item in work.candidates
    )
    review_ms = max(1, round(work.review_ms * rng.uniform(0.9, 1.1)))
    fixture = {
        "candidates": [
            [item.node.node_id, item.node.estimated_execution_ms,
             list(item.closes_obligations)]
            for item in candidates
        ],
        "review_ms": review_ms,
    }
    digest = "sha256:" + hashlib.sha256(
        json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return candidates, review_ms, digest


def wave_latency(costs: list[int], max_wip: int = 3) -> int:
    lanes = [0] * max_wip
    for cost in sorted(costs, reverse=True):
        lane = min(range(max_wip), key=lambda index: (lanes[index], index))
        lanes[lane] += cost
    return max(lanes, default=0)


def choose_v2(candidates: tuple[GrowthCandidate, ...], obligations: tuple[str, ...]):
    """Represent the current static plan: one declared worker per obligation."""
    chosen = []
    for obligation in obligations:
        matches = [item for item in candidates
                   if item.closes_obligations == (obligation,)]
        chosen.append(min(matches, key=lambda item: (
            item.node.estimated_execution_ms, item.node.node_id,
        )))
    return tuple(chosen)


def proof_artifact(work: Workload) -> ProofCarryingArtifact:
    return ProofCarryingArtifact(
        f"artifact:{work.workload_id}", "sha256:" + "a" * 64,
        obligations=tuple(ProofObligation(item, f"verify:{item}")
                          for item in work.obligations),
    )


def choose_cover(work: Workload, candidates: tuple[GrowthCandidate, ...]):
    decision = ProofFrontier(policy_version="sprout-1").route(
        proof_artifact(work), candidates, branch_budget=work.branch_budget, max_wip=3,
    )
    if decision.action != "spawn":
        raise RuntimeError(f"fixture has no bounded proof cover: {work.workload_id}")
    return tuple(item for item in candidates
                 if item.node.node_id in decision.target_node_ids)


def run_cell(work: Workload, arm: str, repetition: int, branches: int) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")
    if branches < 1:
        raise ValueError("branches must be positive")
    candidates, review_ms, fixture_digest = materialize(work, repetition)
    singles = choose_v2(candidates, work.obligations)
    cover = choose_cover(work, candidates)
    pilot_used = arm == "sprout-unconditional"
    shadow_fields: dict[str, Any] = {
        "shadow_planning": False,
        "actual_route": "v2" if arm in {"graphori-v2", "graphori-sprout"} else arm,
        "shadow_action": "",
        "shadow_selected_nodes": [],
        "activation_eligible": False,
        "activation_reason": "",
        "estimated_v2_latency_ms": None,
        "estimated_shadow_latency_ms": None,
        "estimated_gain_ms": None,
        "planning_cost_ms": 0,
        "estimated_v2_ai_nodes": None,
        "estimated_shadow_ai_nodes": None,
        "proof_coverage_delta": 0,
        "shadow_proof_coverage_delta": 0,
        "incorrect_expansion": 0,
        "missed_expansion": 0,
    }
    if arm == "graphori-sprout":
        planning = ProofFrontier(policy_version="sprout-1").plan_conditionally(
            proof_artifact(work), candidates,
            tuple(item.node for item in singles), target_count=branches,
            targets_independent=True, uncertain=False,
            branch_budget=work.branch_budget, max_wip=3,
            min_gain_ms=0, min_gain_ratio=0,
        )
        pilot_used = planning.telemetry.actual_route == "sprout"
        selected_ids = set(planning.actual.target_node_ids)
        selected = tuple(item for item in candidates
                         if item.node.node_id in selected_ids)
        telemetry = planning.telemetry
        shadow_fields = {
            "shadow_planning": True,
            "actual_route": telemetry.actual_route.value,
            "shadow_action": planning.shadow.action.value,
            "shadow_selected_nodes": list(telemetry.shadow_node_ids),
            "activation_eligible": telemetry.activation_eligible,
            "activation_reason": telemetry.activation_reason,
            "estimated_v2_latency_ms": telemetry.estimated_v2_latency_ms,
            "estimated_shadow_latency_ms": telemetry.estimated_shadow_latency_ms,
            "estimated_gain_ms": telemetry.estimated_gain_ms,
            "planning_cost_ms": telemetry.planning_cost_ms,
            "estimated_v2_ai_nodes": telemetry.v2_ai_nodes,
            "estimated_shadow_ai_nodes": telemetry.shadow_ai_nodes,
            "proof_coverage_delta": telemetry.proof_coverage_delta,
            "shadow_proof_coverage_delta": telemetry.shadow_proof_coverage_delta,
            "incorrect_expansion": int(telemetry.incorrect_expansion),
            "missed_expansion": int(telemetry.missed_expansion),
        }
    elif arm in {"sprout-unconditional", "oracle-static"}:
        selected = cover
    else:
        selected = singles

    selected_costs = [item.node.estimated_execution_ms for item in selected]
    target_latency_ms = wave_latency(selected_costs * branches)
    pilot_latency_ms = wave_latency(selected_costs) if pilot_used else 0
    review_latency_ms = (
        wave_latency([review_ms] * branches) if arm == "v1-target-review" else 0
    )
    modeled_latency_ms = target_latency_ms + pilot_latency_ms + review_latency_ms + 10

    agent_per_target = sum(item.node.provider != "generic-process" for item in selected)
    process_per_target = len(selected) - agent_per_target
    activated_nodes = len(selected) * branches
    ai_nodes = agent_per_target * branches
    process_nodes = process_per_target * branches
    pilot_activated_nodes = 0
    pilot_ai_nodes = 0
    pilot_process_nodes = 0
    if pilot_used:
        pilot_activated_nodes = len(selected)
        pilot_ai_nodes = agent_per_target
        pilot_process_nodes = process_per_target
        activated_nodes += pilot_activated_nodes
        ai_nodes += pilot_ai_nodes
        process_nodes += pilot_process_nodes
    elif arm == "v1-target-review":
        activated_nodes += branches
        ai_nodes += branches

    closed = {proof for item in selected for proof in item.closes_obligations}
    return {
        "schema_version": 2,
        "workload": work.workload_id,
        "arm": arm,
        "repetition": repetition,
        "seed": SEED,
        "branches": branches,
        "fixture_digest": fixture_digest,
        "activated_nodes": activated_nodes,
        "ai_nodes": ai_nodes,
        "process_nodes": process_nodes,
        "modeled_latency_ms": modeled_latency_ms,
        "pilot_activated_nodes": pilot_activated_nodes,
        "pilot_ai_nodes": pilot_ai_nodes,
        "pilot_process_nodes": pilot_process_nodes,
        "pilot_modeled_latency_ms": pilot_latency_ms,
        "pilot_used": pilot_used,
        "declared_proofs_closed": len(closed.intersection(work.obligations)) * branches,
        "declared_proofs_total": len(work.obligations) * branches,
        "invalid_fan_in": int(not set(work.obligations) <= closed),
        "selected_nodes": sorted(item.node.node_id for item in selected),
        **shadow_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "build/benchmarks/sprout/raw-results.jsonl",
    )
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--branches", type=int, nargs="+", default=BRANCH_COUNTS)
    args = parser.parse_args()
    if args.repetitions < 1 or any(item < 1 for item in args.branches):
        raise SystemExit("repetitions and branch counts must be positive")
    branch_counts = tuple(dict.fromkeys(args.branches))
    started = time.monotonic()
    rows = [run_cell(work, arm, repetition, branches)
            for repetition in range(1, args.repetitions + 1)
            for work in MATRIX for branches in branch_counts for arm in ARMS]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                           encoding="utf-8")
    print(f"wrote {len(rows)} cells in {time.monotonic() - started:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
