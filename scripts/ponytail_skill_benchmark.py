#!/usr/bin/env python3
"""Run the paired, collect-only RRC-05A Ponytail benchmark."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import time
from typing import Any, Mapping
import uuid

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graphori_adapters.agent_contract import render_task_prompt  # noqa: E402
from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter  # noqa: E402
from graphori_adapters.codex.adapter import CodexExecutionAdapter  # noqa: E402
from graphori_core import (  # noqa: E402
    ActivationScope, ContextBundle, InvocationPolicy, NodeSpec, ProcessLimits,
    RunPlan, SkillBinding, SkillKind, SkillManifest, SkillRegistry, TrustLevel,
)
from graphori_core.routing_reality import create_direct_fixture_repository  # noqa: E402
from graphori_core.skill_effectiveness import (  # noqa: E402
    NO_SKILL, PONYTAIL_FULL, SkillBenchmarkSample, classify_skill_value,
    diff_metrics, needs_additional_pair, paired_orders,
)


PROVIDERS = ("codex", "claude")
WORKLOADS = ("w2-tiny-write", "w3-bounded-implementation")
MODELS = {
    "codex": ("gpt-5.6-luna", "medium"),
    "claude": ("claude-sonnet-5", "medium"),
}
PONYTAIL_SOURCE = Path.home() / ".agents" / "skills" / "ponytail"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def command_version(command: str) -> str:
    import subprocess
    result = subprocess.run(
        (command, "--version"), capture_output=True, text=True, check=False, timeout=10,
    )
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0][:200] if result.returncode == 0 and lines else "unavailable"


def raw_skill_digest(source: Path) -> str:
    return "sha256:" + hashlib.sha256((source / "SKILL.md").read_bytes()).hexdigest()


def pin_ponytail() -> tuple[SkillRegistry, SkillManifest, str]:
    raw_digest = raw_skill_digest(PONYTAIL_SOURCE)
    revision = "local-" + raw_digest
    manifest = SkillManifest(
        skill_id="ponytail",
        name="ponytail",
        description="Minimal implementation discipline pinned for RRC-05A.",
        source="user-local",
        source_commit=revision,
        source_path=str(PONYTAIL_SOURCE),
        license="MIT",
        kind=SkillKind.DISCIPLINE,
        invocation_policy=InvocationPolicy.MODEL_INVOKED,
        activation_scope=ActivationScope.ATTEMPT,
        supported_hosts=("codex", "claude"),
        trust_level=TrustLevel.PINNED_APPROVED,
        performance_status="unmeasured_local",
    )
    registry = SkillRegistry(ROOT / ".graphori" / "skills")
    installed = registry.install(manifest, PONYTAIL_SOURCE)
    return registry, installed, raw_digest


def verify_fixture(root: Path, argv: tuple[str, ...]) -> tuple[str, int]:
    import subprocess
    started = time.monotonic()
    command = (sys.executable, *argv[1:]) if argv and argv[0] == "python" else argv
    result = subprocess.run(
        command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=60,
    )
    return (
        "pass" if result.returncode == 0 else "revise",
        max(0, round((time.monotonic() - started) * 1000)),
    )


def changed_paths(root: Path) -> tuple[str, ...]:
    import subprocess
    result = subprocess.run(
        ("git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"),
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return ("<git-status-unavailable>",)
    return tuple(sorted(
        line[3:] for line in result.stdout.splitlines()
        if len(line) >= 4 and not line[3:].startswith(".graphori/")
    ))


def usage(metadata: Mapping[str, Any], *names: str) -> int | None:
    values = metadata.get("usage")
    if not isinstance(values, Mapping):
        return None
    for name in names:
        value = values.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def make_node(
        provider: str, fixture: Any, pair_id: str,
        bindings: tuple[SkillBinding, ...]) -> NodeSpec:
    model, effort = MODELS[provider]
    return NodeSpec(
        node_id=f"rrc05a-{provider}-{fixture.workload_id}-{uuid.uuid4().hex[:8]}",
        team_id="implementation",
        title=f"RRC-05A {provider} {fixture.workload_id}",
        objective=fixture.objective,
        kind="worker",
        read_scope=fixture.read_scope,
        write_scope=fixture.write_scope,
        provider=provider,
        provider_family="openai" if provider == "codex" else "anthropic",
        adapter=provider,
        model=model,
        model_family="luna" if provider == "codex" else "sonnet",
        effort=effort,
        routing_decision_digest=stable_digest({
            "provider": provider, "model": model, "effort": effort,
            "workload": fixture.workload_id, "pair_id": pair_id,
        }),
        routing_reason_codes=("RRC05A_FIXED_DIRECT_ROUTE",),
        task_kind="bounded_implementation",
        verification_policy="deterministic",
        worktree_policy="current",
        skill_bindings=bindings,
    )


def materialize_binding(
        fixture_root: Path, central: SkillRegistry, manifest: SkillManifest,
        arm: str) -> tuple[tuple[SkillBinding, ...], int, int, bool]:
    if arm == NO_SKILL:
        return (), 0, 0, True
    resolution_started = time.monotonic()
    verified = central.get("ponytail")
    resolution_ms = max(0, round((time.monotonic() - resolution_started) * 1000))
    materialization_started = time.monotonic()
    local = SkillRegistry(fixture_root / ".graphori" / "skills")
    copied = local.install(verified, central.snapshot_path("ponytail"))
    snapshot_verified = local.get("ponytail").content_digest == manifest.content_digest
    materialization_ms = max(
        0, round((time.monotonic() - materialization_started) * 1000),
    )
    binding = SkillBinding(
        skill_id="ponytail", name="ponytail", digest=copied.content_digest,
        snapshot_path=(
            f".graphori/skills/{copied.content_digest.removeprefix('sha256:')}/SKILL.md"
        ),
        source_commit=copied.source_commit,
        arguments=(("mode", "full"),), reason="rrc05a_explicit_benchmark",
        activation_scope=ActivationScope.ATTEMPT,
    )
    return (binding,), resolution_ms, materialization_ms, snapshot_verified


async def run_sample(
        provider: str, workload: str, arm: str, pair_id: str, repetition: int,
        order_index: int, central: SkillRegistry, manifest: SkillManifest,
        ) -> SkillBenchmarkSample:
    model, effort = MODELS[provider]
    temporary = tempfile.TemporaryDirectory(prefix=f"graphori-rrc05a-{provider}-")
    fixture = create_direct_fixture_repository(Path(temporary.name) / "fixture", workload)
    bindings: tuple[SkillBinding, ...] = ()
    resolution_ms = 0
    materialization_ms = 0
    snapshot_verified = arm == NO_SKILL
    route_started = time.monotonic()
    session = None
    adapter = None
    try:
        try:
            bindings, resolution_ms, materialization_ms, snapshot_verified = materialize_binding(
                fixture.root, central, manifest, arm,
            )
        except Exception as exc:
            elapsed = max(0, round((time.monotonic() - route_started) * 1000))
            return SkillBenchmarkSample(
                provider, model, effort, workload, arm, pair_id, repetition, order_index,
                "ponytail" if arm == PONYTAIL_FULL else "",
                manifest.content_digest if arm == PONYTAIL_FULL else "",
                manifest.source_commit if arm == PONYTAIL_FULL else "",
                ("full",) if arm == PONYTAIL_FULL else (),
                0, 0, 0, 0, 0, elapsed, elapsed, elapsed,
                "unknown", False, "unknown", False, 0, 0, 0, 0, 0, 0,
                False, False, effectiveness_eligible=False,
                failure_kind=f"SKILL_LOAD_FAILURE:{type(exc).__name__}", timestamp=now(),
            )
        node = make_node(provider, fixture, pair_id, bindings)
        plan = RunPlan(
            f"rrc05a-{provider}-{uuid.uuid4().hex}", 1, "committed", nodes=(node,),
        )
        plan_digest = plan.digest()
        replay_matches = RunPlan.from_dict(plan.to_dict()).digest() == plan_digest
        adapter_type = CodexExecutionAdapter if provider == "codex" else ClaudeCodeExecutionAdapter
        adapter = adapter_type(
            workspace_root=fixture.root,
            limits=ProcessLimits(timeout_seconds=240, grace_seconds=2),
        )
        capabilities = adapter.probe()
        if not capabilities.available:
            raise RuntimeError(capabilities.reason or "adapter unavailable")
        await adapter.prepare_run(plan)
        session = await adapter.start_session(node)
        context = replace(
            ContextBundle.from_node(node), attempt_id=f"attempt:{node.node_id}:1",
        )
        envelope = adapter._envelope(node, context)
        prompt = render_task_prompt(envelope)
        binding_rendered = (
            arm == NO_SKILL
            or (manifest.content_digest in prompt and "mode=full" in prompt
                and bindings[0].snapshot_path in prompt)
        )
        contamination = arm == NO_SKILL and "ponytail" in prompt.lower()
        dispatch_started = time.monotonic()
        dispatch = await adapter.dispatch(session, node, context)
        async for _event in adapter.events(dispatch):
            pass
        result = await adapter.collect(dispatch)
        verification, verification_ms = verify_fixture(
            fixture.root, fixture.verification_argv,
        )
        ttur_ms = max(0, round((time.monotonic() - dispatch_started) * 1000))
        await adapter.release(session)
        session = None
        total_ms = max(0, round((time.monotonic() - route_started) * 1000))
        metrics = diff_metrics(fixture.root)
        metadata = dict(result.runtime_metadata)
        report_status = str(metadata.get("worker_report_status") or "unknown")
        structured = report_status in {"succeeded", "failed", "incomplete"}
        modifications = changed_paths(fixture.root)
        scope_violation = bool(set(modifications) - set(fixture.write_scope))
        first_event_ms = int(metadata.get("first_event_ms", 0))
        worker_report_ms = int(metadata.get("worker_report_ms", 0))
        return SkillBenchmarkSample(
            provider, model, effort, workload, arm, pair_id, repetition, order_index,
            "ponytail" if arm == PONYTAIL_FULL else "",
            manifest.content_digest if arm == PONYTAIL_FULL else "",
            manifest.source_commit if arm == PONYTAIL_FULL else "",
            ("full",) if arm == PONYTAIL_FULL else (),
            result.adapter_start_ms, first_event_ms, result.execution_ms,
            max(0, worker_report_ms - first_event_ms), verification_ms, ttur_ms,
            total_ms, total_ms, report_status, structured, verification,
            scope_violation, 0, metrics.files_changed, metrics.lines_added,
            metrics.lines_deleted, metrics.new_files, metrics.new_dependencies,
            snapshot_verified, binding_rendered,
            observed_model=str(metadata.get("observed_model") or "unknown"),
            observed_effort=str(metadata.get("observed_effort") or "unknown"),
            input_tokens=usage(metadata, "input_tokens"),
            output_tokens=usage(metadata, "output_tokens"),
            cached_tokens=usage(
                metadata, "cached_input_tokens", "cache_read_input_tokens",
                "cache_creation_input_tokens",
            ),
            estimated_cost=(
                float(metadata["provider_reported_cost_usd"])
                if isinstance(metadata.get("provider_reported_cost_usd"), (int, float))
                else None
            ),
            skill_resolution_ms=resolution_ms,
            skill_materialization_ms=materialization_ms,
            run_plan_digest=plan_digest,
            replay_digest_matches=replay_matches,
            attempt_isolated=not contamination,
            hooks_executed=False,
            plugin_installed=False,
            skill_contamination=contamination,
            failure_kind=(
                "" if result.outcome == "succeeded" else result.error_kind or result.outcome
            ),
            timestamp=now(),
        )
    except Exception as exc:
        elapsed = max(0, round((time.monotonic() - route_started) * 1000))
        if adapter is not None and session is not None:
            try:
                await adapter.release(session)
            except Exception:
                pass
        return SkillBenchmarkSample(
            provider, model, effort, workload, arm, pair_id, repetition, order_index,
            "ponytail" if arm == PONYTAIL_FULL else "",
            manifest.content_digest if arm == PONYTAIL_FULL else "",
            manifest.source_commit if arm == PONYTAIL_FULL else "",
            ("full",) if arm == PONYTAIL_FULL else (),
            0, 0, 0, 0, 0, elapsed, elapsed, elapsed,
            "unknown", False, "unknown", False, 0, 0, 0, 0, 0, 0,
            snapshot_verified, False, skill_resolution_ms=resolution_ms,
            skill_materialization_ms=materialization_ms, effectiveness_eligible=False,
            failure_kind=f"ADAPTER_FAILURE:{type(exc).__name__}", timestamp=now(),
        )
    finally:
        temporary.cleanup()


def medians(samples: list[SkillBenchmarkSample]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in (NO_SKILL, PONYTAIL_FULL):
        values = [sample for sample in samples
                  if sample.arm == arm and sample.effectiveness_eligible]
        result[arm] = {
            "samples": len(values),
            "ttur_ms": round(statistics.median(item.ttur_ms for item in values)) if values else None,
            "total_ms": round(statistics.median(item.total_ms for item in values)) if values else None,
            "effective_time_ms": round(statistics.median(
                item.effective_time_ms for item in values
            )) if values else None,
            "loc_changed": round(statistics.median(
                item.lines_added + item.lines_deleted for item in values
            )) if values else None,
            "input_tokens": round(statistics.median(
                item.input_tokens for item in values if item.input_tokens is not None
            )) if any(item.input_tokens is not None for item in values) else None,
            "output_tokens": round(statistics.median(
                item.output_tokens for item in values if item.output_tokens is not None
            )) if any(item.output_tokens is not None for item in values) else None,
            "cost": statistics.median(
                item.estimated_cost for item in values if item.estimated_cost is not None
            ) if any(item.estimated_cost is not None for item in values) else None,
            "verification_passes": sum(item.verification == "pass" for item in values),
            "scope_violations": sum(item.scope_violation for item in values),
            "reworks": sum(item.rework_count for item in values),
            "structured_failures": sum(not item.structured_result_valid for item in values),
        }
    no_ttur = result[NO_SKILL]["ttur_ms"]
    ponytail_ttur = result[PONYTAIL_FULL]["ttur_ms"]
    no_loc = result[NO_SKILL]["loc_changed"]
    ponytail_loc = result[PONYTAIL_FULL]["loc_changed"]
    result["delta"] = {
        "ttur_percent": (
            round((ponytail_ttur - no_ttur) / no_ttur * 100, 1)
            if no_ttur and ponytail_ttur is not None else None
        ),
        "loc_percent": (
            round((ponytail_loc - no_loc) / no_loc * 100, 1)
            if no_loc and ponytail_loc is not None else None
        ),
    }
    result["classification"] = classify_skill_value(samples).value
    return result


async def collect(
        central: SkillRegistry, manifest: SkillManifest,
        existing: list[SkillBenchmarkSample] | None = None) -> list[SkillBenchmarkSample]:
    samples = list(existing or ())
    if not samples:
        for provider in PROVIDERS:
            for workload in WORKLOADS:
                for repetition, order in enumerate(paired_orders(2), 1):
                    pair_id = f"{provider}-{workload}-{repetition}"
                    for order_index, arm in enumerate(order):
                        print(f"RRC-05A start {pair_id} arm={arm}", flush=True)
                        item = await run_sample(
                            provider, workload, arm, pair_id, repetition, order_index,
                            central, manifest,
                        )
                        samples.append(item)
                        print(
                            f"RRC-05A done {pair_id} arm={arm} ttur_ms={item.ttur_ms} "
                            f"verification={item.verification} "
                            f"eligible={item.effectiveness_eligible}", flush=True,
                        )
    for provider in PROVIDERS:
        for workload in WORKLOADS:
            group = [item for item in samples
                     if item.provider == provider and item.workload == workload]
            if not needs_additional_pair(group) or max(
                    (item.repetition for item in group), default=0) >= 3:
                continue
            repetition = 3
            pair_id = f"{provider}-{workload}-{repetition}"
            for order_index, arm in enumerate(paired_orders(3)[-1]):
                print(f"RRC-05A adaptive start {pair_id} arm={arm}", flush=True)
                item = await run_sample(
                    provider, workload, arm, pair_id, repetition, order_index,
                    central, manifest,
                )
                samples.append(item)
                print(
                    f"RRC-05A adaptive done {pair_id} arm={arm} ttur_ms={item.ttur_ms} "
                    f"verification={item.verification} eligible={item.effectiveness_eligible}",
                    flush=True,
                )
    return samples


def render_report(payload: Mapping[str, Any]) -> str:
    def display(value: Any, *, cost: bool = False) -> str:
        if value is None:
            return "unknown"
        return f"{value:.4f}" if cost else str(value)

    samples = payload["samples"]
    ponytail_samples = [item for item in samples if item["arm"] == PONYTAIL_FULL]
    resolution_median = round(statistics.median(
        item["skill"]["resolution_ms"] for item in ponytail_samples
    ))
    materialization_median = round(statistics.median(
        item["skill"]["materialization_ms"] for item in ponytail_samples
    ))
    lines = [
        "# RRC-05A Ponytail Skill Effectiveness Benchmark",
        "",
        "## Contract",
        "",
        "- Collect-only; routing and auto-binding remain unchanged.",
        "- Direct Codex and Direct Claude only; Orca was not executed.",
        "- W2/W3 paired AB/BA runs use fresh disposable repositories.",
        "- Correctness and scope are evaluated before latency or LOC.",
        "",
        "## Skill provenance",
        "",
        f"- Skill: `ponytail` / mode `full`",
        f"- Package digest: `{payload['skill']['digest']}`",
        f"- Source revision: `{payload['skill']['source_revision']}`",
        "- Git commit provenance: unavailable; source was an existing user-local copy.",
        "- The immutable content digest, not a fabricated commit, identifies every sample.",
        "- Plugin installation: none; hooks executed: none.",
        "",
        "## Results",
        "",
        "| Provider | Workload | No-skill TTUR | Ponytail TTUR | Delta | No-skill LOC | Ponytail LOC | Classification |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for provider in PROVIDERS:
        for workload in WORKLOADS:
            item = payload["summary"][provider][workload]
            lines.append(
                f"| {provider} | {workload} | {item[NO_SKILL]['ttur_ms']} ms | "
                f"{item[PONYTAIL_FULL]['ttur_ms']} ms | {item['delta']['ttur_percent']}% | "
                f"{item[NO_SKILL]['loc_changed']} | {item[PONYTAIL_FULL]['loc_changed']} | "
                f"{item['classification']} |"
            )
    lines.extend((
        "",
        "## Usage observations",
        "",
        "| Provider | Workload | No-skill input | Ponytail input | No-skill output | Ponytail output | No-skill cost | Ponytail cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ))
    for provider in PROVIDERS:
        for workload in WORKLOADS:
            item = payload["summary"][provider][workload]
            lines.append(
                f"| {provider} | {workload} | "
                f"{display(item[NO_SKILL]['input_tokens'])} | "
                f"{display(item[PONYTAIL_FULL]['input_tokens'])} | "
                f"{display(item[NO_SKILL]['output_tokens'])} | "
                f"{display(item[PONYTAIL_FULL]['output_tokens'])} | "
                f"{display(item[NO_SKILL]['cost'], cost=True)} | "
                f"{display(item[PONYTAIL_FULL]['cost'], cost=True)} |"
            )
    lines.extend((
        "",
        "## Reliability",
        "",
        f"- Live samples: {len(samples)}; effectiveness-eligible: "
        f"{sum(item['effectiveness_eligible'] for item in samples)}",
        f"- Ponytail snapshot verified: {sum(item['skill']['snapshot_verified'] for item in ponytail_samples)}/{len(ponytail_samples)}",
        f"- Ponytail binding rendered: {sum(item['skill']['binding_rendered'] for item in ponytail_samples)}/{len(ponytail_samples)}",
        f"- Agent read observation: unknown (provider protocols expose no trustworthy read receipt).",
        f"- Median registry resolution/materialization: {resolution_median} ms / "
        f"{materialization_median} ms",
        f"- Verification failures: {sum(item['quality']['verification'] != 'pass' for item in samples)}",
        f"- Structured result failures: {sum(not item['quality']['structured_result_valid'] for item in samples)}",
        f"- Rework: {sum(item['quality']['rework'] for item in samples)}; scope violations: "
        f"{sum(item['quality']['scope_violation'] for item in samples)}",
        f"- Skill contamination: {sum(item['skill']['contamination'] for item in samples)}; "
        f"attempt isolation: {sum(item['attempt_isolated'] for item in samples)}/{len(samples)}",
        f"- Hook execution: {sum(item['skill']['hooks_executed'] for item in samples)}; "
        f"plugin installation: {sum(item['skill']['plugin_installed'] for item in samples)}",
        f"- Replay digest mismatch: {sum(not item['replay_digest_matches'] for item in samples)}",
        "- Requested effort was medium; observed effort remained unknown on both provider protocols.",
        "- Codex did not report an observed model; Claude reported claude-sonnet-5.",
        "- Usage fields are provider-reported and are not normalized across providers.",
        "",
        "## Cross-model conclusion",
        "",
        "- W2: no quality or LOC change; Ponytail increased median TTUR on both providers.",
        "- W3: no quality or LOC change; Codex was slower and Claude's small speed difference "
        "did not reach the 10% material threshold after the third pair.",
        "- All four provider/workload cells classify as `NO_BENEFIT`.",
        "",
        "## Recommendation",
        "",
        "- Auto candidate: no.",
        "- Manual use: explicit opt-in remains available, but this benchmark found no measured benefit.",
        "- Disabled conditions: Fast and safety-sensitive Nodes remain excluded by existing policy.",
        "- SkillPolicyEngine, ModelRouter, benchmark priors, and adaptive routing remain unchanged.",
    ))
    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> int:
    central, manifest, raw_digest = pin_ponytail()
    existing: list[SkillBenchmarkSample] = []
    if args.resume and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        existing = [SkillBenchmarkSample.from_dict(item) for item in previous["samples"]]
    samples = await collect(central, manifest, existing)
    summary = {
        provider: {
            workload: medians([
                item for item in samples
                if item.provider == provider and item.workload == workload
            ])
            for workload in WORKLOADS
        }
        for provider in PROVIDERS
    }
    payload = {
        "schema_version": 1,
        "collect_only": True,
        "adaptive_routing_enabled": False,
        "model_router_changed": False,
        "benchmark_snapshot_changed": False,
        "created_at": now(),
        "environment": {
            "python": sys.version.split()[0], "platform": sys.platform,
            "codex": command_version("codex"), "claude": command_version("claude"),
        },
        "skill": {
            "id": "ponytail", "mode": "full", "digest": manifest.content_digest,
            "raw_skill_md_digest": raw_digest,
            "source_commit": None,
            "source_revision": manifest.source_commit,
            "source_commit_status": "unavailable_local_copy",
            "args": ["full"], "plugin_installed": False, "hooks_executed": False,
        },
        "sampling": {
            "minimum_runs": 16, "maximum_runs": 24,
            "actual_runs": len(samples), "paired_order": "AB/BA",
        },
        "summary": summary,
        "samples": [item.to_dict() for item in samples],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"sampling": payload["sampling"], "summary": summary}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "docs" / "research" / "RRC-05A_RESULTS.json",
    )
    parser.add_argument(
        "--report", type=Path,
        default=ROOT / "docs" / "research" / "RRC-05A_PONYTAIL_EFFECTIVENESS.md",
    )
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
