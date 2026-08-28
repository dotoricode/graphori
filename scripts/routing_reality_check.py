#!/usr/bin/env python3
"""Run RRC-01 against disposable repositories and emit bounded telemetry."""

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
from typing import Any
import uuid

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter  # noqa: E402
from graphori_adapters.codex.adapter import CodexExecutionAdapter  # noqa: E402
from graphori_adapters.orca import OrcaExecutionAdapter  # noqa: E402
from graphori_core import ContextBundle, NodeSpec, RunPlan  # noqa: E402
from graphori_core.routing_reality import (  # noqa: E402
    FailureDomain, TelemetrySample, create_fixture_repository,
    required_sample_count, summarize_routes,
)


ROUTES = ("direct-codex", "direct-claude", "orca-codex", "orca-claude")
MODELS = {
    "codex": ("gpt-5.6-terra", "medium"),
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


def orca_version() -> str:
    result = subprocess.run(
        ["orca", "status", "--json"], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=10,
    )
    try:
        status = result_object(json.loads(result.stdout))
    except (json.JSONDecodeError, RuntimeError):
        return "unavailable"
    runtime = status.get("runtime", {})
    return str(
        status.get("appVersion")
        or (runtime.get("appVersion") if isinstance(runtime, dict) else None)
        or status.get("version")
        or "unknown"
    )


def result_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value.get("ok"):
        raise RuntimeError(f"Orca command failed: {value!r}")
    result = value.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Orca result is not an object")
    return result


def create_orca_workspace() -> tuple[str, Path]:
    name = f"graphori-rrc-{uuid.uuid4().hex[:8]}"
    completed = subprocess.run(
        ["orca", "worktree", "create", "--name", name, "--no-parent",
         "--setup", "skip", "--json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    value = json.loads(completed.stdout) if completed.stdout.strip() else None
    result = result_object(value)
    worktree = result.get("worktree", result)
    if not isinstance(worktree, dict):
        raise RuntimeError("Orca worktree result is malformed")
    worktree_id = str(worktree.get("id", ""))
    path = Path(str(worktree.get("path", worktree.get("worktreePath", ""))))
    if not worktree_id or not path.is_dir():
        raise RuntimeError("Orca worktree identity/path is missing")
    return worktree_id, path


def remove_orca_workspace(worktree_id: str) -> None:
    subprocess.run(
        ["orca", "worktree", "rm", "--worktree", f"id:{worktree_id}",
         "--force", "--json"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


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


def verify_fixture(repo: Path) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        timeout=60,
    )
    return "pass" if result.returncode == 0 else "revise"


def adapter_health(adapter: Any, available: bool) -> str:
    if not available:
        return "unavailable"
    health = getattr(adapter, "health", None)
    if health is None:
        return "ready"
    snapshot = health.snapshot()
    relevant = {
        key: value for key, value in snapshot.items()
        if key in {"create_run", "create_task", "dispatch", "delivery", "release"}
    }
    if any(value == "unavailable" for value in relevant.values()):
        return "unavailable"
    if any(value == "degraded" for value in relevant.values()):
        return "degraded"
    return "ready"


def unavailable_sample(route: str, provider: str, model: str, effort: str,
                       reason: str, cold: bool) -> TelemetrySample:
    identity = {"route": route, "provider": provider, "model": model,
                "effort": effort, "task": "bounded_write"}
    digest = stable_digest(identity)
    return TelemetrySample(
        route, f"rrc:{digest[-16:]}", digest, provider, route, model, "unknown",
        effort, "unknown", "bounded_implementation", "low", False, cold,
        0, 0, 0, 0, 0, 0, 0, 0, 0, "outcome_unknown", "unknown", False,
        0, False, "unavailable", FailureDomain.ADAPTER, now(),
        failure_reason=reason[:240],
    )


async def run_attempt(route: str, *, cold: bool, read_only: bool) -> TelemetrySample:
    provider = "codex" if route.endswith("codex") else "claude"
    model, effort = MODELS[provider]
    is_orca = route.startswith("orca-")
    worktree_id = ""
    temporary: tempfile.TemporaryDirectory[str] | None = None
    started = time.monotonic()
    try:
        if is_orca:
            worktree_id, workspace = create_orca_workspace()
            fixture = create_fixture_repository(workspace / "rrc-fixture")
            adapter: Any = OrcaExecutionAdapter(
                workspace_root=workspace, delivery_timeout_ms=120_000,
                worktree_selector=f"id:{worktree_id}",
            )
            scope_prefix = "rrc-fixture/"
        else:
            temporary = tempfile.TemporaryDirectory(prefix="graphori-rrc-")
            fixture = create_fixture_repository(Path(temporary.name) / "fixture")
            workspace = fixture
            adapter = (CodexExecutionAdapter if provider == "codex"
                       else ClaudeCodeExecutionAdapter)(workspace_root=workspace)
            scope_prefix = ""

        capabilities = adapter.probe()
        if not capabilities.available:
            return unavailable_sample(
                route, provider, model, effort, capabilities.reason, cold,
            )
        task_name = "readonly" if read_only else "bounded-write"
        identity = {
            "route": route, "provider": provider, "model": model,
            "effort": effort, "task": task_name,
        }
        decision_digest = stable_digest(identity)
        if read_only:
            objective = (
                f"Read {scope_prefix}pyproject.toml and report the project name and "
                "requires-python value. Do not modify any file."
            )
            read_scope = (f"{scope_prefix}pyproject.toml",)
            write_scope: tuple[str, ...] = ()
        else:
            objective = (
                f"Implement add(a, b) in {scope_prefix}src/math_utils.py and run "
                f"{scope_prefix}tests/test_math_utils.py. Modify only the declared files."
            )
            read_scope = (
                f"{scope_prefix}src/math_utils.py",
                f"{scope_prefix}tests/test_math_utils.py",
            )
            write_scope = read_scope
        node = NodeSpec(
            f"rrc-{provider}-{task_name}-{uuid.uuid4().hex[:8]}",
            "research" if read_only else "implementation",
            f"RRC {provider} {task_name}", objective, "worker",
            read_scope=read_scope, write_scope=write_scope,
            provider=provider, provider_family=("openai" if provider == "codex"
                                                else "anthropic"),
            adapter=provider, model=model,
            model_family=("terra" if provider == "codex" else "sonnet"),
            effort=effort, routing_decision_digest=decision_digest,
            routing_reason_codes=("RRC_FIXED_ROUTE",),
            task_kind="research" if read_only else "bounded_implementation",
            verification_policy="independent" if not read_only else "deterministic",
            worktree_policy="current",
        )
        run_id = f"rrc-{route}-{uuid.uuid4().hex}"
        plan = RunPlan(run_id, 1, "committed", nodes=(node,))
        await adapter.prepare_run(plan)
        session = await adapter.start_session(node)
        dispatch = await adapter.dispatch(
            session, node, ContextBundle(
                objective=objective, attempt_id=f"attempt:{node.node_id}:1",
                read_scope=read_scope, write_scope=write_scope,
            ),
        )
        completion_seen = False
        async for event in adapter.events(dispatch):
            completion_seen = completion_seen or event.event_type == "worker_finished"
            if capabilities.supports_delivery_ack:
                await adapter.acknowledge(event)
        result = await adapter.collect(dispatch)
        cleanup_started = time.monotonic()
        await adapter.release(session)
        cleanup_ms = max(0, round((time.monotonic() - cleanup_started) * 1000))
        total_ms = max(0, round((time.monotonic() - started) * 1000))
        metadata = dict(result.runtime_metadata)
        observed_model = str(metadata.get("observed_model") or "unknown")
        observed_effort = str(metadata.get("observed_effort") or "unknown")
        modifications = changed_paths(fixture)
        allowed = {"src/math_utils.py", "tests/test_math_utils.py"}
        violation = bool(set(modifications) - allowed) if not read_only else bool(modifications)
        verification = "not_required" if read_only else verify_fixture(fixture)
        structured_valid = (
            metadata.get("worker_report_status") in {"succeeded", "failed", "incomplete"}
            if not is_orca else completion_seen and result.outcome == "succeeded"
        )
        health = adapter_health(adapter, True)
        failure = FailureDomain.NONE
        if violation:
            failure = FailureDomain.POLICY
        elif health != "ready":
            failure = FailureDomain.ADAPTER
        elif result.outcome != "succeeded":
            failure = (
                FailureDomain.MODEL
                if structured_valid and metadata.get("worker_report_status") == "failed"
                else FailureDomain.PROVIDER
            )
        elif verification == "revise":
            failure = FailureDomain.VERIFICATION
        premium_ids = {"gpt-5.6-sol", "claude-opus-5"}
        if observed_model in premium_ids:
            failure = FailureDomain.POLICY
            health = "degraded"
        return TelemetrySample(
            route, f"rrc:{decision_digest[-16:]}", decision_digest,
            provider, route, model, observed_model, effort, observed_effort,
            "research" if read_only else "bounded_implementation", "low",
            read_only, cold,
            result.queue_wait_ms,
            result.adapter_start_ms,
            int(metadata.get("provider_start_ms", 0)),
            int(metadata.get("first_event_ms", metadata.get("delivery_wait_ms", 0))),
            int(metadata.get("worker_report_ms", metadata.get("delivery_wait_ms", 0))),
            result.execution_ms or int(metadata.get("delivery_wait_ms", 0)),
            result.collect_ms,
            int(metadata.get("cleanup_ms", cleanup_ms)),
            total_ms,
            result.outcome,
            verification,
            structured_valid,
            0,
            violation,
            health,
            failure,
            now(),
            int(metadata.get("orca_run_setup_ms", 0)),
            int(metadata.get("orca_task_setup_ms", 0)),
            int(metadata.get("dispatch_start_ms", 0)),
            int(metadata.get("delivery_wait_ms", 0)),
            int(metadata.get("ack_ms", 0)),
            int(metadata.get("release_ms", 0)),
            failure_reason=(
                str(result.error_kind or "")[:240]
                or (f"worker_report_status={metadata.get('worker_report_status')}"
                    if failure is FailureDomain.MODEL else "")
            ),
        )
    except Exception as exc:
        return unavailable_sample(route, provider, model, effort, type(exc).__name__, cold)
    finally:
        if worktree_id:
            remove_orca_workspace(worktree_id)
        if temporary is not None:
            temporary.cleanup()


async def main_async(routes: tuple[str, ...], output: Path) -> int:
    samples: list[TelemetrySample] = []
    for route in routes:
        cold = await run_attempt(route, cold=True, read_only=True)
        samples.append(cold)
        if (cold.worker_outcome == "outcome_unknown"
                and cold.failure_domain is FailureDomain.ADAPTER):
            continue
        samples.append(await run_attempt(route, cold=False, read_only=False))
        totals = [item.total_ms for item in samples if item.route_id == route]
        if required_sample_count(totals) == 3:
            samples.append(await run_attempt(route, cold=False, read_only=False))
    report = summarize_routes(samples)
    payload = {
        "schema_version": 1,
        "collect_only": True,
        "adaptive_routing_enabled": False,
        "created_at": now(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "codex": command_version(("codex", "--version")),
            "claude": command_version(("claude", "--version")),
            "orca": orca_version(),
        },
        "samples": [item.to_dict() for item in samples],
        "summary": report.to_dict(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--routes", default=",".join(ROUTES),
        help="comma-separated route ids",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "docs" / "research" / "RRC-01-RESULTS.json",
    )
    args = parser.parse_args()
    routes = tuple(item.strip() for item in args.routes.split(",") if item.strip())
    unknown = set(routes) - set(ROUTES)
    if unknown:
        parser.error(f"unknown routes: {', '.join(sorted(unknown))}")
    return asyncio.run(main_async(routes, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
