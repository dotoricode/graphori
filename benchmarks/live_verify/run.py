#!/usr/bin/env python3
"""Run the paired v2 versus Live Verify wall-clock benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from graphori_adapters.direct import RoutedExecutionAdapter  # noqa: E402
from graphori_adapters.generic.adapter import (  # noqa: E402
    GenericProcessAdapter, ProcessCommand,
)
from graphori_adapters.live_verify import LiveVerifyAdapter  # noqa: E402
from graphori_core.ports import ContextBundle  # noqa: E402
from graphori_core.process_supervisor import ProcessLimits  # noqa: E402
from graphori_core.run_plan import NodeSpec, RunPlan  # noqa: E402


PYTHON = sys.executable


async def run_once(root: Path, *, arm: str, stale_fault: bool = False) -> dict[str, object]:
    worker = NodeSpec(
        "i1", "implementation", "Implement", "Implement", "worker",
        adapter="worker", provider="worker", write_scope=("result.txt",),
    )
    verifier = NodeSpec(
        "v1", "verification", "Verify", "Verify", "verifier",
        dependencies=("i1",), adapter="generic-process",
        provider="generic-process", read_scope=(".",),
    )
    plan = RunPlan("run-live", 1, "committed", nodes=(worker, verifier))
    if stale_fault:
        worker_script = (
            "from pathlib import Path; import time; "
            "Path('result.txt').write_text('ready'); time.sleep(0.3); "
            "Path('late.txt').write_text('changed'); time.sleep(0.2)"
        )
    else:
        worker_script = (
            "from pathlib import Path; import time; "
            "Path('result.txt').write_text('ready'); time.sleep(0.9)"
        )
    limits = ProcessLimits(timeout_seconds=5, grace_seconds=0.1)
    worker_adapter = GenericProcessAdapter(
        workspace_root=root,
        commands={"i1": ProcessCommand((PYTHON, "-c", worker_script), limits=limits)},
    )
    verify_command = ProcessCommand(
        (PYTHON, "-c", "from pathlib import Path; "
         "assert Path('result.txt').read_text() == 'ready'; "
         "import time; time.sleep(0.4)"),
        verdict_from_exit=True, criterion_ids=("AC-01",), limits=limits,
    )
    verifier_adapter = GenericProcessAdapter(
        workspace_root=root, commands={"v1": verify_command},
    )
    routed = RoutedExecutionAdapter({
        "worker": worker_adapter, "generic-process": verifier_adapter,
    })
    adapter = (LiveVerifyAdapter(
        routed, workspace_root=root, commands={"v1": verify_command},
        poll_seconds=0.01, settle_seconds=0.03,
    ) if arm == "live-verify" else routed)
    await adapter.prepare_run(plan)
    started = time.perf_counter()
    worker_session = await adapter.start_session(worker)
    worker_dispatch = await adapter.dispatch(
        worker_session, worker, ContextBundle.from_node(worker),
    )
    async for _event in adapter.events(worker_dispatch):
        pass
    await adapter.collect(worker_dispatch)
    await adapter.release(worker_session)
    verifier_session = await adapter.start_session(verifier)
    verifier_dispatch = await adapter.dispatch(
        verifier_session, verifier, ContextBundle.from_node(verifier),
    )
    events = [event async for event in adapter.events(verifier_dispatch)]
    result = await adapter.collect(verifier_dispatch)
    await adapter.release(verifier_session)
    live_metrics = adapter.metrics() if arm == "live-verify" else {
        "live_verify_attempt_count": 0,
        "live_verify_eligible_count": 0,
        "live_verify_eligible_rate": 0.0,
        "live_verify_pass_candidate_count": 0,
        "live_verify_reuse_count": 0,
        "live_verify_reuse_rate": 0.0,
        "live_verify_fallback_count": 0,
        "live_verify_fallback_reasons": {},
    }
    verdicts = [event for event in events if event.event_type == "verdict_recorded"]
    return {
        "arm": arm,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "correct": bool(verdicts and verdicts[-1].payload.get("verdict") == "pass"),
        "proof_reused": bool(result.runtime_metadata.get("live_verify_reused")),
        "stale_fault": stale_fault,
        "ai_sessions": 0,
        "fresh_input_tokens": 0,
        **live_metrics,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def bootstrap_lower_bound(pairs: list[tuple[float, float]], *, seed: int = 20260831) -> float:
    rng = random.Random(seed)
    estimates = []
    for _ in range(5_000):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        before = statistics.median(item[0] for item in sample)
        after = statistics.median(item[1] for item in sample)
        estimates.append((before - after) / before * 100)
    return percentile(estimates, 0.025)


async def benchmark(repetitions: int, fault_repetitions: int) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    pairs: list[tuple[float, float]] = []
    for repetition in range(1, repetitions + 1):
        order = ("graphori-v2", "live-verify") if repetition % 2 else (
            "live-verify", "graphori-v2")
        measured: dict[str, float] = {}
        for arm in order:
            with tempfile.TemporaryDirectory() as directory:
                row = await run_once(Path(directory), arm=arm)
            row["repetition"] = repetition
            rows.append(row)
            measured[arm] = float(row["duration_ms"])
        pairs.append((measured["graphori-v2"], measured["live-verify"]))
    fault_rows = []
    for repetition in range(1, fault_repetitions + 1):
        with tempfile.TemporaryDirectory() as directory:
            row = await run_once(Path(directory), arm="live-verify", stale_fault=True)
        row["repetition"] = repetition
        fault_rows.append(row)
    before = [item[0] for item in pairs]
    after = [item[1] for item in pairs]
    live_rows = [row for row in rows if row["arm"] == "live-verify"]
    eligible = sum(int(row["live_verify_eligible_count"]) for row in live_rows)
    attempts = sum(int(row["live_verify_attempt_count"]) for row in live_rows)
    candidates = sum(int(row["live_verify_pass_candidate_count"]) for row in live_rows)
    reuses = sum(int(row["live_verify_reuse_count"]) for row in live_rows)
    fallbacks = sum(int(row["live_verify_fallback_count"]) for row in live_rows)
    fallback_reasons: dict[str, int] = {}
    for row in (*live_rows, *fault_rows):
        for reason, count in dict(row["live_verify_fallback_reasons"]).items():
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + int(count)
    median_reduction = (1 - statistics.median(after) / statistics.median(before)) * 100
    p95_reduction = (1 - percentile(after, 0.95) / percentile(before, 0.95)) * 100
    checks = {
        "correctness_equal": all(row["correct"] for row in rows),
        "stale_proofs_reused": sum(bool(row["proof_reused"]) for row in fault_rows),
        "ai_sessions_increase": 0,
        "fresh_input_tokens_increase": 0,
        "median_reduction_percent": round(median_reduction, 3),
        "p95_reduction_percent": round(p95_reduction, 3),
        "bootstrap_95_lower_percent": round(bootstrap_lower_bound(pairs), 3),
        "live_verify_attempt_count": attempts,
        "live_verify_eligible_count": eligible,
        "live_verify_eligible_rate": round(eligible / attempts, 3) if attempts else 0.0,
        "live_verify_pass_candidate_count": candidates,
        "live_verify_reuse_count": reuses,
        "live_verify_reuse_rate": round(reuses / candidates, 3) if candidates else 0.0,
        "live_verify_fallback_count": fallbacks,
        "fallback_reason_breakdown": dict(sorted(fallback_reasons.items())),
    }
    passed = (
        checks["correctness_equal"]
        and checks["stale_proofs_reused"] == 0
        and median_reduction >= 25
        and p95_reduction >= 15
        and checks["bootstrap_95_lower_percent"] > 20
    )
    return {
        "schema_version": 1,
        "fixture": "write-then-report-tail with repeatable deterministic verification",
        "repetitions": repetitions,
        "fault_repetitions": fault_repetitions,
        "checks": checks,
        "passed": passed,
        "rows": rows,
        "fault_rows": fault_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--fault-repetitions", type=int, default=10)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "build/benchmarks/live_verify/results.json",
    )
    args = parser.parse_args()
    if args.repetitions < 3 or args.fault_repetitions < 1:
        parser.error("use at least 3 paired repetitions and 1 fault repetition")
    result = asyncio.run(benchmark(args.repetitions, args.fault_repetitions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "fixture", "repetitions", "fault_repetitions", "checks", "passed",
    )}, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
