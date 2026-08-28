#!/usr/bin/env python3
"""Validate and summarize the public three-arm benchmark JSONL."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Any


PROVIDERS = ("codex", "claude")
ARMS = ("direct", "v1-style", "graphori-v2")
TASKS = ("normalize-tags", "config-parser", "retry-policy", "dependency-order")


def load(path: Path) -> list[dict[str, Any]]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"record {number} is not an object")
        records.append(value)
    return records


def sum_or_unknown(rows: list[dict[str, Any]], section: str, key: str):
    values = [(row.get(section) or {}).get(key) for row in rows]
    return sum(values) if values and all(isinstance(value, (int, float)) for value in values) else None


def validate(records: list[dict[str, Any]], repetitions: int) -> None:
    expected = {
        (provider, arm, task, repetition)
        for provider in PROVIDERS for arm in ARMS for task in TASKS
        for repetition in range(1, repetitions + 1)
    }
    actual = {
        (row.get("provider"), row.get("arm"), row.get("task_id"), row.get("repetition"))
        for row in records
    }
    if len(actual) != len(records):
        raise ValueError("duplicate benchmark cells")
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"benchmark matrix mismatch; missing={missing}, extra={extra}")
    commits = {row.get("source_commit") for row in records}
    if len(commits) != 1 or None in commits:
        raise ValueError("all records must use one explicit source commit")
    for row in records:
        usage = row.get("usage") or {}
        total = usage.get("total_input_tokens")
        fresh = usage.get("fresh_input_tokens")
        cached = usage.get("cached_input_tokens")
        if all(isinstance(value, int) for value in (total, fresh, cached)) and total != fresh + cached:
            raise ValueError(f"input token identity failed for {row.get('run_id')}")


def summarize(records: list[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    validate(records, repetitions)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["provider"], row["arm"])].append(row)
    providers: dict[str, Any] = {}
    for provider in PROVIDERS:
        arms: dict[str, Any] = {}
        for arm in ARMS:
            rows = grouped[(provider, arm)]
            ttur = [row["quality"]["ttur_seconds"] for row in rows]
            arms[arm] = {
                "runs": len(rows),
                "successful_runs": sum(row["outcome"] == "succeeded" for row in rows),
                "hidden_tests_passed": sum_or_unknown(rows, "quality", "hidden_tests_passed"),
                "hidden_tests_total": sum_or_unknown(rows, "quality", "hidden_tests_total"),
                "ai_sessions": sum_or_unknown(rows, "usage", "ai_sessions"),
                "median_ttur_seconds": round(statistics.median(ttur), 3),
                "total_input_tokens": sum_or_unknown(rows, "usage", "total_input_tokens"),
                "cached_input_tokens": sum_or_unknown(rows, "usage", "cached_input_tokens"),
                "fresh_input_tokens": sum_or_unknown(rows, "usage", "fresh_input_tokens"),
                "output_tokens": sum_or_unknown(rows, "usage", "output_tokens"),
                "cost_usd": sum_or_unknown(rows, "usage", "cost_usd"),
                "rework_count": sum_or_unknown(rows, "quality", "rework_count"),
                "scope_violations": sum_or_unknown(rows, "quality", "scope_violations"),
                "claim_matches_hidden": sum(row.get("claim_matches_hidden") is True for row in rows),
                "unknown_outcomes": sum(row["outcome"] == "unknown" for row in rows),
            }
        providers[provider] = arms
    return {
        "schema_version": 1,
        "matrix": {"providers": 2, "arms": 3, "tasks": 4,
                   "repetitions": repetitions, "runs": len(records)},
        "source_commit": records[0]["source_commit"],
        "providers": providers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path,
                        default=Path("benchmarks/three_arm/raw-results.jsonl"))
    parser.add_argument("--output", type=Path,
                        default=Path("benchmarks/three_arm/results.json"))
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    result = summarize(load(args.raw), args.repetitions)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
