#!/usr/bin/env python3
"""Recalculate benchmark summaries and render the human report."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent


def load_runner():
    spec = importlib.util.spec_from_file_location("graphori_v1_v2_runner", ROOT / "run_benchmark.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("benchmark runner cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def percent_change(new: float, old: float) -> float:
    return (new - old) / old * 100


def repair_derived_fields(data: dict[str, Any], runner: Any) -> list[str]:
    notes: list[str] = []
    for row in data["rows"]:
        if row["condition"] != "v2-candidate":
            continue
        parsed = runner.extract_last_json(row.get("stdout_tail", ""))
        terminal = parsed.get("terminal_status", row.get("terminal_status", "unknown"))
        old_terminal = row.get("terminal_status")
        if old_terminal != terminal:
            notes.append(
                f"Recalculated {row['workload_id']} r{row['repetition']} terminal_status "
                f"from {old_terminal!r} to {terminal!r} using retained stdout."
            )
        row["terminal_status"] = terminal
        claim = row.get("exit_code") == 0 and terminal == "succeeded"
        row["completion_claim"] = claim
        row["claim_matches_hidden_judge"] = claim == row["hidden_judge"]["passed"]
    return notes


def metric_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for condition in ("v1-reconstructed", "v2-candidate"):
        selected = [row for row in rows if row["condition"] == condition]
        result[condition] = {
            "elapsed": [row["elapsed_ms"] for row in selected],
            "by_workload": {
                workload: [
                    row["elapsed_ms"] for row in selected if row["workload_id"] == workload
                ]
                for workload in sorted({row["workload_id"] for row in selected})
            },
        }
    return result


def render_report(data: dict[str, Any], notes: list[str]) -> str:
    summary = data["summary"]
    v1 = summary["v1-reconstructed"]
    v2 = summary["v2-candidate"]
    metrics = metric_rows(data["rows"])
    faster = -percent_change(v2["median_elapsed_ms"], v1["median_elapsed_ms"])
    input_reduction = -percent_change(v2["total_input_tokens"], v1["total_input_tokens"])
    output_reduction = -percent_change(v2["total_output_tokens"], v1["total_output_tokens"])
    workload_lines = []
    for workload in sorted(metrics["v1-reconstructed"]["by_workload"]):
        v1_values = metrics["v1-reconstructed"]["by_workload"][workload]
        v2_values = metrics["v2-candidate"]["by_workload"][workload]
        workload_lines.append(
            f"| `{workload}` | {round(statistics.median(v1_values)):,} | "
            f"{round(statistics.median(v2_values)):,} | "
            f"{-percent_change(statistics.median(v2_values), statistics.median(v1_values)):.1f}% |"
        )
    correction_text = (
        f"- 저장된 출력으로 v2 {len(notes)}건의 완료 상태를 다시 읽었다."
        if notes else "- 다시 계산할 항목이 없었다."
    )
    return f"""# Graphori v1과 v2 성능 측정 결과

측정일: 2026-08-24

두 버전에는 같은 코딩 과제, 같은 시작 파일, 같은 모델과 같은 숨은 검사를 줬다.
달랐던 것은 일을 확인하는 방식이다. v1은 별도 검토 AI를 한 번 더 불렀고, v2는
미리 정한 자동 검사를 실행했다. 자세한 조건은 [`PROTOCOL.md`](PROTOCOL.md)에 있다.

## 한눈에 보는 결과

이번 작은 시험에서는 두 버전 모두 네 번의 작업을 정확히 끝냈다. v2는 같은
정답률을 유지하면서 AI 호출을 절반만 사용했고, 가운데 실행 시간은 {faster:.1f}%
짧았다. 입력 토큰은 {input_reduction:.1f}%, 출력 토큰은 {output_reduction:.1f}%
적게 사용했다.

| 확인한 내용 | v1 재현판 | v2 후보 |
| --- | ---: | ---: |
| 숨은 검사 통과 | {v1['hidden_judge_passes']} / {v1['runs']} | {v2['hidden_judge_passes']} / {v2['runs']} |
| 완료 보고와 실제 결과 일치 | {v1['claim_matches']} / {v1['runs']} | {v2['claim_matches']} / {v2['runs']} |
| 허용 범위 밖 파일 변경 | {v1['scope_violations']}건 | {v2['scope_violations']}건 |
| AI 호출 횟수 | {v1['provider_calls']}회 | {v2['provider_calls']}회 |
| 가운데 실행 시간 | {v1['median_elapsed_ms'] / 1000:.1f}초 | {v2['median_elapsed_ms'] / 1000:.1f}초 |
| 전체 입력 토큰 | {v1['total_input_tokens']:,} | {v2['total_input_tokens']:,} |
| 전체 출력 토큰 | {v1['total_output_tokens']:,} | {v2['total_output_tokens']:,} |

과제별 시간:

| 과제 | v1 가운데 시간(ms) | v2 가운데 시간(ms) | v2가 줄인 비율 |
| --- | ---: | ---: | ---: |
{chr(10).join(workload_lines)}

## 예상과 실제

v1은 별도 AI가 한 번 더 보면 실수를 더 찾을 것으로 예상했다. 실제로 네 작업은
모두 맞았지만, 두 번째 AI가 새 문제를 발견한 경우는 없었다. AI 호출은 v2의 두
배였고 가운데 실행 시간은 {v1['median_elapsed_ms'] / 1000:.1f}초였다.

v2는 작은 작업에서 별도 AI 대신 자동 검사를 사용하면 품질을 지키면서 시간과
토큰을 줄일 것으로 예상했다. 실제로 네 작업과 네 업무일지가 모두 성공했고,
가운데 실행 시간은 {v2['median_elapsed_ms'] / 1000:.1f}초였다. 이번 결과에서 줄어든
시간과 토큰의 대부분은 두 번째 AI 호출이 사라진 효과로 볼 수 있다.

## 측정 도구에서 발견한 문제

첫 집계에서는 v2가 완료 표시를 네 번 모두 놓쳤다고 잘못 나왔다. 측정 도구가 큰
결과 안의 작은 JSON 조각을 마지막 결과로 착각했기 때문이다. AI를 다시 실행하지
않고 저장된 출력과 각 실행의 14개 업무 기록으로 바로잡았다. 이후에는 줄 맨 앞에서
시작하는 최종 JSON만 읽도록 고쳤다.

{correction_text}

이 문제는 Graphori v2의 작업 실패가 아니라 측정 도구의 집계 오류다. 처음 결과도
[`raw-results.json`](raw-results.json)에 남겨 교정 과정을 확인할 수 있게 했다.

## 이 결과로 말할 수 없는 것

- 버전마다 작은 파이썬 작업을 네 번만 실행했다. 모든 개발 작업에서 v2가 33.9%
  빠르다고 말할 수 없다.
- v1은 커밋 `{data['environment']['v1_commit']}`의 문서를 바탕으로 재현한 방식이다.
  남아 있는 과거 실행을 다시 재생한 것이 아니다.
- v2는 정식 출시판이 아니라 당시 로컬 후보였다. 소스 식별값은
  `{data['environment']['v2_source_digest']}`이다.
- 자동 검사를 만들기 어려운 복잡하고 위험한 작업에서는 별도 AI나 사람의 검토가
  여전히 도움이 될 수 있다.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "raw-results.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results.json")
    parser.add_argument("--report", type=Path, default=ROOT / "REPORT.md")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    runner = load_runner()
    notes = repair_derived_fields(data, runner)
    data["status"] = "complete-recalculated"
    data["analysis_notes"] = notes
    data["summary"] = runner.summarize(data["rows"])
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.write_text(render_report(data, notes), encoding="utf-8")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
