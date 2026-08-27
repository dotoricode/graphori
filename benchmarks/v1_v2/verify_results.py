#!/usr/bin/env python3
"""Independently verify the retained v1/v2 benchmark artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    runner = load(ROOT / "run_benchmark.py", "graphori_benchmark_runner_verify")
    raw = json.loads((ROOT / "raw-results.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")

    assert raw["status"] == "complete"
    assert result["status"] == "complete-recalculated"
    assert len(raw["rows"]) == len(result["rows"]) == 8
    assert raw["environment"] == result["environment"]
    assert raw["execution_order"] == result["execution_order"]
    assert len(result["analysis_notes"]) == 4

    cells = {}
    for row in result["rows"]:
        assert "infrastructure_error" not in row
        key = (row["condition"], row["workload_id"])
        cells.setdefault(key, set()).add(row["repetition"])
        assert row["visible_check"]["passed"] is True
        assert row["hidden_judge"]["passed"] is True
        assert row["scope_violation"] is False
        assert row["claim_matches_hidden_judge"] is True
        if row["condition"] == "v2-candidate":
            assert row["terminal_status"] == "succeeded"
            assert row["journal"]["event_count"] == 14
            parsed = runner.extract_last_json(row["stdout_tail"])
            assert parsed["terminal_status"] == "succeeded"
    assert len(cells) == 4
    assert all(repetitions == {1, 2} for repetitions in cells.values())

    expected_summary = runner.summarize(result["rows"])
    assert result["summary"] == expected_summary
    v1 = expected_summary["v1-reconstructed"]
    v2 = expected_summary["v2-candidate"]
    assert v1["provider_calls"] == 8 and v2["provider_calls"] == 4
    assert v1["hidden_judge_passes"] == v2["hidden_judge_passes"] == 4
    assert v2["median_elapsed_ms"] < v1["median_elapsed_ms"]
    assert v2["total_input_tokens"] < v1["total_input_tokens"]
    assert v2["total_output_tokens"] < v1["total_output_tokens"]

    for text in (
        "33.9%",
        "41.2%",
        "48.5초",
        "32.1초",
        "측정 도구에서 발견한 문제",
    ):
        assert text in report, text

    print("benchmark artifact verification: PASS")
    print("rows=8 cells=4 repetitions_per_cell=2 hidden_passes=8 scope_violations=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
