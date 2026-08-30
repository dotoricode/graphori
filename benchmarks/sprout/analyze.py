#!/usr/bin/env python3
"""Validate and summarize the deterministic Sprout routing-model benchmark."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARMS = (
    "v1-target-review", "graphori-v2", "sprout-unconditional",
    "graphori-sprout", "oracle-static",
)
WORKLOADS = (
    "regional-collection", "repository-audit", "release-preflight", "api-import",
)
BRANCH_COUNTS = (1, 2, 4, 8, 16)


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _arm_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runs": len(cells),
        "declared_proofs_closed": sum(row["declared_proofs_closed"] for row in cells),
        "declared_proofs_total": sum(row["declared_proofs_total"] for row in cells),
        "invalid_fan_in": sum(row["invalid_fan_in"] for row in cells),
        "activated_nodes": sum(row["activated_nodes"] for row in cells),
        "ai_nodes": sum(row["ai_nodes"] for row in cells),
        "process_nodes": sum(row["process_nodes"] for row in cells),
        "pilots_used": sum(row["pilot_used"] for row in cells),
        "median_modeled_latency_ms": round(statistics.median(
            row["modeled_latency_ms"] for row in cells
        ), 3),
    }


def _reduction(before: float, after: float) -> float:
    return round((before - after) / before * 100, 3)


def summarize(rows: list[dict[str, Any]], repetitions: int,
              branch_counts: tuple[int, ...] = BRANCH_COUNTS) -> dict[str, Any]:
    expected = {
        (arm, workload, repetition, branches)
        for arm in ARMS for workload in WORKLOADS
        for repetition in range(1, repetitions + 1) for branches in branch_counts
    }
    actual = {
        (row["arm"], row["workload"], row["repetition"], row["branches"])
        for row in rows
    }
    if actual != expected or len(rows) != len(expected):
        raise ValueError("benchmark matrix is incomplete or contains duplicates")

    fixtures: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in rows:
        fixtures[(row["workload"], row["repetition"])].add(row["fixture_digest"])
    if any(len(digests) != 1 for digests in fixtures.values()):
        raise ValueError("arms or branch counts received different latency fixtures")

    sensitivity = {}
    for branches in branch_counts:
        branch_rows = [row for row in rows if row["branches"] == branches]
        grouped = {
            arm: [row for row in branch_rows if row["arm"] == arm] for arm in ARMS
        }
        arms = {arm: _arm_summary(grouped[arm]) for arm in ARMS}
        sprout = arms["graphori-sprout"]
        v2 = arms["graphori-v2"]
        paired_oracle = {
            (row["workload"], row["repetition"]): row
            for row in grouped["oracle-static"]
        }
        overheads = [
            row["modeled_latency_ms"]
            - paired_oracle[(row["workload"], row["repetition"])]["modeled_latency_ms"]
            for row in grouped["sprout-unconditional"]
        ]
        sensitivity[str(branches)] = {
            "arms": arms,
            "comparisons": {
                "sprout_vs_v2_reduction_percent": {
                    metric: _reduction(v2[metric], sprout[metric])
                    for metric in (
                        "activated_nodes", "ai_nodes", "median_modeled_latency_ms",
                    )
                },
                "unconditional_vs_oracle_static": {
                    "activated_nodes_overhead": (
                        arms["sprout-unconditional"]["activated_nodes"]
                        - arms["oracle-static"]["activated_nodes"]
                    ),
                    "ai_nodes_overhead": (
                        arms["sprout-unconditional"]["ai_nodes"]
                        - arms["oracle-static"]["ai_nodes"]
                    ),
                    "median_paired_latency_overhead_ms": round(
                        statistics.median(overheads), 3
                    ),
                },
            },
        }

    all_arms = [entry for point in sensitivity.values() for entry in point["arms"].values()]
    if any(cell["declared_proofs_closed"] != cell["declared_proofs_total"]
           or cell["invalid_fan_in"] for cell in all_arms):
        raise ValueError("declared proof coverage invariant failed")
    return {
        "schema_version": 2,
        "matrix": {
            "arms": len(ARMS),
            "workloads": len(WORKLOADS),
            "repetitions": repetitions,
            "branch_counts": list(branch_counts),
            "runs": len(rows),
        },
        "sensitivity": sensitivity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", type=Path,
        default=ROOT / "build/benchmarks/sprout/raw-results.jsonl",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "build/benchmarks/sprout/results.json",
    )
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--branches", type=int, nargs="+", default=BRANCH_COUNTS)
    args = parser.parse_args()
    branch_counts = tuple(dict.fromkeys(args.branches))
    result = summarize(load(args.raw), args.repetitions, branch_counts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
