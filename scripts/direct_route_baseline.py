#!/usr/bin/env python3
"""Run RRC-04 direct-route diagnostics and collect-only baselines."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping
import uuid

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter  # noqa: E402
from graphori_adapters.claude.protocol import ClaudeProtocolParser  # noqa: E402
from graphori_adapters.codex.adapter import CodexExecutionAdapter  # noqa: E402
from graphori_core import ContextBundle, NodeSpec, ProcessLimits, RunPlan  # noqa: E402
from graphori_core.routing_reality import (  # noqa: E402
    FailureDomain,
    TelemetrySample,
    classify_self_report,
    create_direct_fixture_repository,
    summarize_direct_baseline,
    summarize_routes,
)


ROUTES = ("direct-codex", "direct-claude")
WORKLOADS = ("w1-read", "w2-tiny-write", "w3-bounded-implementation")
MODELS = {
    "codex": ("gpt-5.6-luna", "medium"),
    "claude": ("claude-sonnet-5", "medium"),
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def command_version(argv: tuple[str, ...]) -> str:
    result = subprocess.run(
        argv, capture_output=True, text=True, check=False, timeout=10,
    )
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0][:200] if result.returncode == 0 and lines else "unavailable"


def changed_paths(repo: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return ("<git-status-unavailable>",)
    return tuple(sorted(
        line[3:].strip() for line in result.stdout.splitlines() if len(line) >= 4
    ))


def verify_fixture(root: Path, workload: str, argv: tuple[str, ...]) -> tuple[str, int]:
    started = time.monotonic()
    if workload == "w1-read":
        content = (root / "pyproject.toml").read_text(encoding="utf-8")
        passed = (
            'name = "graphori-rrc04-fixture"' in content
            and 'requires-python = ">=3.11"' in content
            and changed_paths(root) == ()
        )
    else:
        command = (sys.executable, *argv[1:]) if argv and argv[0] == "python" else argv
        result = subprocess.run(
            command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=60,
        )
        passed = result.returncode == 0
    elapsed = max(0, round((time.monotonic() - started) * 1000))
    return ("pass" if passed else "revise"), elapsed


def usage_fields(metadata: Mapping[str, Any]) -> dict[str, Any]:
    usage = metadata.get("usage")
    if not isinstance(usage, Mapping) or not usage:
        return {
            "usage_status": "unknown", "input_tokens": None,
            "output_tokens": None, "cached_tokens": None,
        }

    def integer(*names: str) -> int | None:
        for name in names:
            value = usage.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    return {
        "usage_status": "known",
        "input_tokens": integer("input_tokens"),
        "output_tokens": integer("output_tokens"),
        "cached_tokens": integer(
            "cached_input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
        ),
    }


def make_node(provider: str, fixture: Any, decision_digest: str) -> NodeSpec:
    model, effort = MODELS[provider]
    return NodeSpec(
        f"rrc04-{provider}-{fixture.workload_id}-{uuid.uuid4().hex[:8]}",
        "research" if not fixture.write_scope else "implementation",
        f"RRC-04 {provider} {fixture.workload_id}", fixture.objective, "worker",
        read_scope=fixture.read_scope,
        write_scope=fixture.write_scope,
        provider=provider,
        provider_family="openai" if provider == "codex" else "anthropic",
        adapter=provider,
        model=model,
        model_family="luna" if provider == "codex" else "sonnet",
        effort=effort,
        routing_decision_digest=decision_digest,
        routing_reason_codes=("RRC04_FIXED_DIRECT_ROUTE",),
        task_kind="research" if not fixture.write_scope else "bounded_implementation",
        verification_policy="deterministic",
        worktree_policy="current",
    )


async def run_attempt(route: str, workload: str, *, cold: bool) -> TelemetrySample:
    provider = route.removeprefix("direct-")
    model, effort = MODELS[provider]
    identity = {
        "route": route, "provider": provider, "model": model,
        "effort": effort, "workload": workload,
    }
    decision_digest = stable_digest(identity)
    started = time.monotonic()
    temporary = tempfile.TemporaryDirectory(prefix=f"graphori-rrc04-{provider}-")
    try:
        fixture = create_direct_fixture_repository(Path(temporary.name) / "fixture", workload)
        adapter_class = CodexExecutionAdapter if provider == "codex" else ClaudeCodeExecutionAdapter
        adapter = adapter_class(
            workspace_root=fixture.root,
            limits=ProcessLimits(timeout_seconds=240, grace_seconds=2),
        )
        capabilities = adapter.probe()
        if not capabilities.available:
            raise RuntimeError(capabilities.reason or "adapter unavailable")
        node = make_node(provider, fixture, decision_digest)
        plan = RunPlan(f"rrc04-{route}-{uuid.uuid4().hex}", 1, "committed", nodes=(node,))
        await adapter.prepare_run(plan)
        session = await adapter.start_session(node)
        dispatch = await adapter.dispatch(
            session, node,
            ContextBundle(
                objective=node.objective,
                attempt_id=f"attempt:{node.node_id}:1",
                read_scope=node.read_scope,
                write_scope=node.write_scope,
            ),
        )
        async for _event in adapter.events(dispatch):
            pass
        result = await adapter.collect(dispatch)
        verification, verification_ms = verify_fixture(
            fixture.root, workload, fixture.verification_argv,
        )
        await adapter.release(session)
        total_ms = max(0, round((time.monotonic() - started) * 1000))
        metadata = dict(result.runtime_metadata)
        report_status = str(metadata.get("worker_report_status") or "unknown")
        structured_valid = report_status in {"succeeded", "failed", "incomplete"}
        disagreement = (
            report_status in {"failed", "incomplete"} and verification == "pass"
        )
        modifications = changed_paths(fixture.root)
        scope_violation = bool(set(modifications) - set(fixture.write_scope))
        failure = FailureDomain.NONE
        health = "ready"
        if scope_violation:
            failure, health = FailureDomain.POLICY, "degraded"
        elif not structured_valid:
            failure, health = FailureDomain.PROVIDER, "degraded"
        elif disagreement:
            failure, health = FailureDomain.MODEL, "degraded"
        elif verification == "revise":
            failure, health = FailureDomain.VERIFICATION, "degraded"
        elif result.outcome != "succeeded":
            failure, health = FailureDomain.PROVIDER, "degraded"
        first_event_ms = int(metadata.get("first_event_ms", 0))
        worker_report_ms = int(metadata.get("worker_report_ms", 0))
        sample = TelemetrySample(
            route, f"rrc04:{decision_digest[-16:]}", decision_digest,
            provider, route, model, str(metadata.get("observed_model") or "unknown"),
            effort, str(metadata.get("observed_effort") or "unknown"),
            node.task_kind, "low", not fixture.write_scope, cold,
            result.queue_wait_ms, result.adapter_start_ms,
            int(metadata.get("provider_start_ms", first_event_ms)), first_event_ms,
            worker_report_ms, result.execution_ms, result.collect_ms,
            int(metadata.get("cleanup_ms", 0)), total_ms,
            result.outcome, verification, structured_valid, 0,
            scope_violation, health, failure, now(),
            failure_reason=(
                f"worker_report_status={report_status}" if disagreement
                else str(result.error_kind or "")[:240]
            ),
            workload_id=workload,
            process_spawn_ms=result.adapter_start_ms,
            structured_result_ms=max(0, worker_report_ms - first_event_ms),
            verification_ms=verification_ms,
            ttur_ms=total_ms,
            effective_time_ms=total_ms,
            worker_report_status=report_status,
            self_report_disagreement=disagreement,
            estimated_cost=(
                float(metadata["provider_reported_cost_usd"])
                if isinstance(metadata.get("provider_reported_cost_usd"), (int, float))
                else None
            ),
            **usage_fields(metadata),
        )
        classify_self_report(sample)
        return sample
    except Exception as exc:
        elapsed = max(0, round((time.monotonic() - started) * 1000))
        return TelemetrySample(
            route, f"rrc04:{decision_digest[-16:]}", decision_digest,
            provider, route, model, "unknown", effort, "unknown",
            "unknown", "low", workload == "w1-read", cold,
            0, 0, 0, 0, 0, 0, 0, 0, elapsed,
            "outcome_unknown", "unknown", False, 0, False,
            "unavailable", FailureDomain.ADAPTER, now(),
            failure_reason=type(exc).__name__, workload_id=workload,
            ttur_ms=elapsed, effective_time_ms=elapsed,
        )
    finally:
        temporary.cleanup()


def sanitize(value: Any, root: Path) -> Any:
    if isinstance(value, str):
        return value.replace(str(root), "<fixture>").replace(str(Path.home()), "<home>")
    if isinstance(value, list):
        return [sanitize(item, root) for item in value]
    if isinstance(value, dict):
        return {
            key: (
                "<session>" if key == "session_id"
                else "<redacted>" if key == "signature"
                else sanitize(item, root)
            )
            for key, item in value.items()
        }
    return value


def capture_claude_protocol(
        stdout_path: Path, stderr_path: Path, *,
        allow_bounded_tests: bool = True) -> dict[str, Any]:
    """Capture one sanitized Claude W2 stream through the exact adapter command."""

    temporary = tempfile.TemporaryDirectory(prefix="graphori-rrc04-claude-protocol-")
    try:
        fixture = create_direct_fixture_repository(
            Path(temporary.name) / "fixture", "w2-tiny-write",
        )
        adapter = ClaudeCodeExecutionAdapter(
            workspace_root=fixture.root,
            limits=ProcessLimits(timeout_seconds=240, grace_seconds=2),
        )
        capabilities = adapter.probe()
        if not capabilities.available:
            raise RuntimeError(capabilities.reason or "Claude adapter unavailable")
        identity = {"route": "direct-claude", "workload": fixture.workload_id,
                    "model": MODELS["claude"][0], "effort": MODELS["claude"][1]}
        node = make_node("claude", fixture, stable_digest(identity))
        context = ContextBundle(
            objective=node.objective, attempt_id="attempt:rrc04:claude-protocol:1",
            read_scope=node.read_scope, write_scope=node.write_scope,
        )
        with tempfile.TemporaryDirectory(prefix="graphori-rrc04-schema-") as schema_dir:
            command = adapter._command(
                adapter._envelope(node, context), Path(schema_dir) / "schema.json", node,
            )
            if not allow_bounded_tests and "--allowedTools" in command:
                index = command.index("--allowedTools")
                command = (*command[:index], *command[index + 2:])
            process = adapter.supervisor.run(
                command, workspace_root=fixture.root,
                env=adapter.process_env,
                env_allowlist=adapter.process_env_allowlist,
                limits=adapter.limits,
            )
        parsed = ClaudeProtocolParser().parse(process.stdout)
        sanitized_lines = []
        for raw in process.stdout.splitlines():
            if raw.strip():
                sanitized_lines.append(json.dumps(
                    sanitize(json.loads(raw), fixture.root),
                    ensure_ascii=False, sort_keys=True,
                ))
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("\n".join(sanitized_lines) + "\n", encoding="utf-8")
        stderr_path.write_text(
            process.stderr.decode("utf-8", errors="replace").replace(
                str(fixture.root), "<fixture>",
            ),
            encoding="utf-8",
        )
        verification, verification_ms = verify_fixture(
            fixture.root, fixture.workload_id, fixture.verification_argv,
        )
        return {
            "process_exit": process.exit_code,
            "structured_report": parsed.report is not None,
            "worker_report_status": parsed.report.status if parsed.report else "missing",
            "observed_model": parsed.observed_model or "unknown",
            "observed_git_delta": list(changed_paths(fixture.root)),
            "verification": verification,
            "verification_ms": verification_ms,
            "stdout_digest": "sha256:" + hashlib.sha256(process.stdout).hexdigest(),
            "stderr_digest": "sha256:" + hashlib.sha256(process.stderr).hexdigest(),
        }
    finally:
        temporary.cleanup()


async def run_baseline(warm_runs: int) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for route in ROUTES:
        for workload in WORKLOADS:
            phases = ("cold", *(f"warm-{index + 1}" for index in range(warm_runs)))
            for phase in phases:
                print(f"RRC-04 start {route} {workload} {phase}", flush=True)
                sample = await run_attempt(route, workload, cold=phase == "cold")
                samples.append(sample)
                print(
                    f"RRC-04 done {route} {workload} {phase} "
                    f"outcome={sample.worker_outcome} verification="
                    f"{sample.verification_outcome} total_ms={sample.total_ms}",
                    flush=True,
                )
    return samples


async def main_async(args: argparse.Namespace) -> int:
    protocol = capture_claude_protocol(args.protocol_stdout, args.protocol_stderr)
    if args.diagnose_only:
        print(json.dumps(protocol, indent=2, sort_keys=True))
        return 0
    samples = await run_baseline(args.warm_runs)
    payload = {
        "schema_version": 1,
        "collect_only": True,
        "adaptive_routing_enabled": False,
        "benchmark_snapshot_changed": False,
        "created_at": now(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "codex": command_version(("codex", "--version")),
            "claude": command_version(("claude", "--version")),
        },
        "claude_protocol_probe": protocol,
        "samples": [sample.to_dict() for sample in samples],
        "direct_baseline": summarize_direct_baseline(samples).to_dict(),
        "route_health": summarize_routes(samples).to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "claude_protocol_probe": protocol,
        "direct_baseline": payload["direct_baseline"],
        "route_health": payload["route_health"],
    }, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warm-runs", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--diagnose-only", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "docs" / "research" / "RRC-04_RESULTS.json",
    )
    parser.add_argument(
        "--protocol-stdout", type=Path,
        default=ROOT / "docs" / "research" / "RRC-04_CLAUDE_PROTOCOL_SANITIZED.jsonl",
    )
    parser.add_argument(
        "--protocol-stderr", type=Path,
        default=ROOT / "docs" / "research" / "RRC-04_CLAUDE_STDERR_SANITIZED.txt",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
