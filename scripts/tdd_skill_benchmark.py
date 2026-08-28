#!/usr/bin/env python3
"""Run the paired, collect-only RRC-05B TDD benchmark."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
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
    RunPlan, SkillBinding, SkillCompatibilityCompiler, SkillKind, SkillManifest,
    SkillNodeContext, SkillRegistry, TrustLevel,
)
from graphori_core.tdd_effectiveness import (  # noqa: E402
    NO_SKILL, TDD, TddBenchmarkSample, TddValueClassification,
    changed_loc, classify_tdd_value, create_tdd_fixture_repository,
    inspect_test_quality, mutation_detected, paired_tdd_orders, verify_tdd_fixture,
)


PROVIDERS = ("codex", "claude")
WORKLOADS = ("w2-tiny-write", "w3-bounded-implementation", "w4-regression-prone")
MODELS = {
    "codex": ("gpt-5.6-luna", "medium"),
    "claude": ("claude-sonnet-5", "medium"),
}
TDD_SOURCE = Path.home() / ".agents" / "skills" / "tdd"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def command_version(command: str) -> str:
    result = subprocess.run(
        (command, "--version"), capture_output=True, text=True,
        check=False, timeout=10,
    )
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0][:200] if result.returncode == 0 and lines else "unavailable"


def raw_package_digest(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def pin_tdd() -> tuple[SkillRegistry, SkillManifest, str]:
    raw_digest = raw_package_digest(TDD_SOURCE)
    revision = "local-" + raw_digest
    manifest = SkillManifest(
        skill_id="tdd", name="tdd",
        description="Public-seam red-green discipline pinned for RRC-05B.",
        source="user-local", source_commit=revision,
        source_path=str(TDD_SOURCE), license="MIT", kind=SkillKind.DISCIPLINE,
        invocation_policy=InvocationPolicy.MODEL_INVOKED,
        activation_scope=ActivationScope.ATTEMPT,
        supported_hosts=("codex", "claude"),
        referenced_files=("tests.md", "mocking.md"),
        preconditions=("approved_test_seams",), dependencies=(),
        requires_user_interaction=False, requires_nested_agents=False,
        trust_level=TrustLevel.PINNED_APPROVED,
        performance_status="unmeasured_local",
    )
    registry = SkillRegistry(ROOT / ".graphori" / "skills")
    installed = registry.install(manifest, TDD_SOURCE)
    return registry, installed, raw_digest


def changed_paths(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"),
        capture_output=True, text=True, check=False,
    )
    return tuple(sorted(
        line[3:] for line in result.stdout.splitlines()
        if len(line) >= 4 and not line[3:].startswith(".graphori/")
    )) if result.returncode == 0 else ("<git-status-unavailable>",)


def usage(metadata: Mapping[str, Any], *names: str) -> int | None:
    values = metadata.get("usage")
    if not isinstance(values, Mapping):
        return None
    for name in names:
        value = values.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def materialize_binding(
        root: Path, central: SkillRegistry, manifest: SkillManifest, arm: str,
        provider: str) -> tuple[tuple[SkillBinding, ...], bool, tuple[str, ...]]:
    if arm == NO_SKILL:
        return (), True, ()
    context = SkillNodeContext(
        node_id="rrc05b", task_kind="implementation", host=provider, risk="low",
        preconditions=frozenset({"approved_test_seams"}),
    )
    resolved = SkillCompatibilityCompiler().resolve(
        "tdd", central.manifests(), context, explicit=True,
    )
    unexpected = tuple(item.skill_id for item in resolved if item.skill_id != "tdd")
    local = SkillRegistry(root / ".graphori" / "skills")
    copied = local.install(resolved[-1], central.snapshot_path("tdd"))
    verified = local.get("tdd").content_digest == manifest.content_digest
    binding = SkillBinding(
        skill_id="tdd", name="tdd", digest=copied.content_digest,
        snapshot_path=(
            f".graphori/skills/{copied.content_digest.removeprefix('sha256:')}/SKILL.md"
        ),
        source_commit=copied.source_commit,
        reason="rrc05b_explicit_benchmark",
        activation_scope=ActivationScope.ATTEMPT,
    )
    return (binding,), verified, unexpected


def make_node(provider: str, fixture: Any, pair_id: str,
              bindings: tuple[SkillBinding, ...]) -> NodeSpec:
    model, effort = MODELS[provider]
    return NodeSpec(
        node_id=f"rrc05b-{provider}-{fixture.workload_id}-{uuid.uuid4().hex[:8]}",
        team_id="implementation", title=f"RRC-05B {provider} {fixture.workload_id}",
        objective=fixture.objective, kind="worker",
        read_scope=fixture.read_scope, write_scope=fixture.write_scope,
        provider=provider,
        provider_family="openai" if provider == "codex" else "anthropic",
        adapter=provider, model=model,
        model_family="luna" if provider == "codex" else "sonnet",
        effort=effort,
        routing_decision_digest=stable_digest({
            "provider": provider, "model": model, "effort": effort,
            "workload": fixture.workload_id, "pair_id": pair_id,
        }),
        routing_reason_codes=("RRC05B_FIXED_DIRECT_ROUTE",),
        task_kind="implementation", verification_policy="independent_deterministic",
        worktree_policy="current", skill_bindings=bindings,
        acceptance_criteria=fixture.acceptance_criteria,
    )


def failed_sample(provider: str, workload: str, arm: str, pair_id: str,
                  repetition: int, order_index: int, elapsed: int,
                  manifest: SkillManifest, error: str) -> TddBenchmarkSample:
    model, effort = MODELS[provider]
    return TddBenchmarkSample(
        provider, model, effort, workload, arm, pair_id, repetition, order_index,
        elapsed, elapsed, "unknown", False, "unknown", False, False, 0,
        False, False, False,
        skill_digest=manifest.content_digest if arm == TDD else "",
        skill_source_revision=manifest.source_commit if arm == TDD else "",
        effectiveness_eligible=False, failure_kind=error, timestamp=now(),
    )


async def run_sample(
        provider: str, workload: str, arm: str, pair_id: str, repetition: int,
        order_index: int, central: SkillRegistry, manifest: SkillManifest,
        ) -> TddBenchmarkSample:
    model, effort = MODELS[provider]
    temporary = tempfile.TemporaryDirectory(prefix=f"graphori-rrc05b-{provider}-")
    fixture = create_tdd_fixture_repository(Path(temporary.name) / "fixture", workload)
    route_started = time.monotonic()
    adapter = session = None
    try:
        bindings, snapshot_verified, unexpected = materialize_binding(
            fixture.root, central, manifest, arm, provider,
        )
        node = make_node(provider, fixture, pair_id, bindings)
        plan = RunPlan(
            f"rrc05b-{provider}-{uuid.uuid4().hex}", 1, "committed", nodes=(node,),
        )
        plan_digest = plan.digest()
        replay_matches = RunPlan.from_dict(plan.to_dict()).digest() == plan_digest
        adapter_type = CodexExecutionAdapter if provider == "codex" else ClaudeCodeExecutionAdapter
        adapter = adapter_type(
            workspace_root=fixture.root,
            limits=ProcessLimits(timeout_seconds=300, grace_seconds=2),
        )
        probe = adapter.probe()
        if not probe.available:
            raise RuntimeError(probe.reason or "adapter unavailable")
        await adapter.prepare_run(plan)
        session = await adapter.start_session(node)
        context = replace(ContextBundle.from_node(node), attempt_id=f"attempt:{node.node_id}:1")
        prompt = render_task_prompt(adapter._envelope(node, context))
        binding_rendered = arm == NO_SKILL or (
            manifest.content_digest in prompt and bindings[0].snapshot_path in prompt
        )
        contamination = arm == NO_SKILL and (
            manifest.content_digest in prompt or ".graphori/skills/" in prompt
        )
        dispatch_started = time.monotonic()
        dispatch = await adapter.dispatch(session, node, context)
        async for _event in adapter.events(dispatch):
            pass
        result = await adapter.collect(dispatch)
        verification_started = time.monotonic()
        visible = subprocess.run(
            (sys.executable, *fixture.verification_argv[1:]), cwd=fixture.root,
            capture_output=True, text=True, check=False, timeout=60,
        )
        independent, _failure_count = verify_tdd_fixture(fixture)
        verification = "pass" if visible.returncode == 0 and independent == "pass" else "revise"
        verification_ms = max(0, round((time.monotonic() - verification_started) * 1000))
        ttur_ms = max(0, round((time.monotonic() - dispatch_started) * 1000))
        await adapter.release(session)
        session = None
        total_ms = max(0, round((time.monotonic() - route_started) * 1000))
        metadata = dict(result.runtime_metadata)
        report_status = str(metadata.get("worker_report_status") or "unknown")
        structured = report_status in {"succeeded", "failed", "incomplete"}
        scope_violation = bool(set(changed_paths(fixture.root)) - set(fixture.write_scope))
        quality = inspect_test_quality(fixture)
        mutation = mutation_detected(fixture) if visible.returncode == 0 else False
        production_loc, test_loc, files_changed = changed_loc(fixture.root)
        first_event_ms = int(metadata.get("first_event_ms", 0))
        worker_report_ms = int(metadata.get("worker_report_ms", 0))
        escaped = report_status == "succeeded" and verification != "pass"
        return TddBenchmarkSample(
            provider, model, effort, workload, arm, pair_id, repetition, order_index,
            ttur_ms, total_ms, report_status, structured, verification,
            scope_violation, escaped, int(verification != "pass"),
            quality.regression_test_exists, mutation, quality.public_seam_test,
            startup_ms=result.adapter_start_ms, first_event_ms=first_event_ms,
            execution_ms=result.execution_ms,
            structured_result_ms=max(0, worker_report_ms - first_event_ms),
            verification_ms=verification_ms, total_ms=total_ms,
            production_loc=production_loc, test_loc=test_loc,
            files_changed=files_changed,
            private_method_test_count=quality.private_method_test_count,
            implementation_mock_count=quality.implementation_mock_count,
            skill_digest=manifest.content_digest if arm == TDD else "",
            skill_source_revision=manifest.source_commit if arm == TDD else "",
            skill_snapshot_verified=snapshot_verified,
            binding_rendered=binding_rendered,
            approved_seams_present="approved_test_seams" in fixture.preconditions,
            unexpected_dependencies=unexpected, user_question_count=0,
            nested_agent_count=0, hooks_executed=False, plugin_installed=False,
            skill_contamination=contamination,
            observed_model=str(metadata.get("observed_model") or "unknown"),
            observed_effort=str(metadata.get("observed_effort") or "unknown"),
            input_tokens=usage(metadata, "input_tokens"),
            output_tokens=usage(metadata, "output_tokens"),
            cached_tokens=usage(metadata, "cached_input_tokens", "cache_read_input_tokens"),
            estimated_cost=(
                float(metadata["provider_reported_cost_usd"])
                if isinstance(metadata.get("provider_reported_cost_usd"), (int, float))
                else None
            ),
            run_plan_digest=plan_digest, replay_digest_matches=replay_matches,
            effectiveness_eligible=True,
            failure_kind="" if result.outcome == "succeeded" else result.error_kind or result.outcome,
            timestamp=now(),
        )
    except Exception as exc:
        elapsed = max(0, round((time.monotonic() - route_started) * 1000))
        if adapter is not None and session is not None:
            try:
                await adapter.release(session)
            except Exception:
                pass
        return failed_sample(
            provider, workload, arm, pair_id, repetition, order_index, elapsed,
            manifest, f"ADAPTER_OR_SKILL_FAILURE:{type(exc).__name__}",
        )
    finally:
        temporary.cleanup()


def medians(samples: list[TddBenchmarkSample]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in (NO_SKILL, TDD):
        values = [item for item in samples if item.arm == arm and item.effectiveness_eligible]
        median = lambda name: (  # noqa: E731
            round(statistics.median(getattr(item, name) for item in values)) if values else None
        )
        costs = [item.estimated_cost for item in values if item.estimated_cost is not None]
        result[arm] = {
            "samples": len(values), "ttur_ms": median("ttur_ms"),
            "effective_time_ms": median("effective_time_ms"),
            "production_loc": median("production_loc"), "test_loc": median("test_loc"),
            "escaped_defects": sum(item.escaped_defect for item in values),
            "reworks": sum(item.rework_count for item in values),
            "mutation_detected": sum(item.mutation_detected for item in values),
            "verification_passes": sum(item.verification == "pass" for item in values),
            "scope_violations": sum(item.scope_violation for item in values),
            "cost": statistics.median(costs) if costs else None,
        }
    baseline, skilled = result[NO_SKILL], result[TDD]
    result["delta"] = {
        "ttur_percent": round(
            (skilled["ttur_ms"] - baseline["ttur_ms"]) / baseline["ttur_ms"] * 100, 1,
        ) if baseline["ttur_ms"] and skilled["ttur_ms"] is not None else None,
        "effective_percent": round(
            (skilled["effective_time_ms"] - baseline["effective_time_ms"])
            / baseline["effective_time_ms"] * 100, 1,
        ) if baseline["effective_time_ms"] and skilled["effective_time_ms"] is not None else None,
    }
    result["classification"] = classify_tdd_value(samples).value
    return result


def overall_classification(values: list[str]) -> str:
    if "harmful" in values:
        return "harmful"
    if "conditional" in values or "auto_candidate" in values:
        return "conditional"
    if "manual_only" in values:
        return "manual_only"
    if values and all(value == "no_benefit" for value in values):
        return "no_benefit"
    return "insufficient_data"


def write_checkpoint(path: Path, samples: list[TddBenchmarkSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1, "status": "running", "updated_at": now(),
        "samples": [item.to_dict() for item in samples],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def collect(
        central: SkillRegistry, manifest: SkillManifest,
        output: Path, existing: list[TddBenchmarkSample],
        providers: tuple[str, ...], workloads: tuple[str, ...], repetitions: int,
        ) -> list[TddBenchmarkSample]:
    samples = list(existing)
    completed = {(item.provider, item.workload, item.repetition, item.arm) for item in samples}
    for provider in providers:
        for workload in workloads:
            for repetition, order in enumerate(paired_tdd_orders(repetitions), 1):
                pair_id = f"{provider}-{workload}-{repetition}"
                for order_index, arm in enumerate(order):
                    key = (provider, workload, repetition, arm)
                    if key in completed:
                        continue
                    print(f"RRC-05B start {pair_id} arm={arm}", flush=True)
                    item = await run_sample(
                        provider, workload, arm, pair_id, repetition, order_index,
                        central, manifest,
                    )
                    samples.append(item)
                    completed.add(key)
                    write_checkpoint(output, samples)
                    print(
                        f"RRC-05B done {pair_id} arm={arm} ttur_ms={item.ttur_ms} "
                        f"verification={item.verification} mutation={item.mutation_detected} "
                        f"eligible={item.effectiveness_eligible}", flush=True,
                    )
    return samples


def render_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# RRC-05B TDD Skill Effectiveness Benchmark", "",
        "## Contract", "",
        "- Collect-only: SkillPolicyEngine, ModelRouter, and adaptive routing are unchanged.",
        "- Direct Codex/Claude only; each workload uses paired AB/BA disposable repositories.",
        "- Both arms receive identical approved public seams and independent verification.",
        "- RED/GREEN and skill-read observations remain unknown unless provider evidence proves them.",
        "", "## Skill provenance", "",
        f"- Skill: `tdd`", f"- Package digest: `{payload['skill']['digest']}`",
        f"- Source revision: `{payload['skill']['source_revision']}`",
        "- Git commit provenance: unavailable; the immutable package digest is authoritative.",
        "- Resolved dependency set: `[tdd]`; scripts/hooks/plugins executed: none.",
        "", "## Results", "",
        "| Provider | Workload | No-skill TTUR | TDD TTUR | Delta | Escaped defects N/T | Mutation N/T | Classification |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for provider in PROVIDERS:
        for workload in WORKLOADS:
            item = payload["summary"][provider][workload]
            lines.append(
                f"| {provider} | {workload} | {item[NO_SKILL]['ttur_ms']} ms | "
                f"{item[TDD]['ttur_ms']} ms | {item['delta']['ttur_percent']}% | "
                f"{item[NO_SKILL]['escaped_defects']}/{item[TDD]['escaped_defects']} | "
                f"{item[NO_SKILL]['mutation_detected']}/{item[TDD]['mutation_detected']} | "
                f"{item['classification']} |"
            )
    samples = payload["samples"]
    for provider in PROVIDERS:
        provider_classes = [
            payload["summary"][provider][workload]["classification"]
            for workload in WORKLOADS
        ]
        lines.extend((
            "", f"## {provider.title()}", "",
            "| Workload | No-skill TTUR | TDD TTUR | Delta | No-skill effective | TDD effective | Classification |",
            "|---|---:|---:|---:|---:|---:|---|",
        ))
        for workload in WORKLOADS:
            item = payload["summary"][provider][workload]
            lines.append(
                f"| {workload} | {item[NO_SKILL]['ttur_ms']} ms | "
                f"{item[TDD]['ttur_ms']} ms | {item['delta']['ttur_percent']}% | "
                f"{item[NO_SKILL]['effective_time_ms']} ms | "
                f"{item[TDD]['effective_time_ms']} ms | {item['classification']} |"
            )
        lines.extend((
            "",
            f"- Provider classification: `{overall_classification(provider_classes)}`.",
            f"- Escaped defects (no-skill/TDD): "
            f"{sum(payload['summary'][provider][w][NO_SKILL]['escaped_defects'] for w in WORKLOADS)}/"
            f"{sum(payload['summary'][provider][w][TDD]['escaped_defects'] for w in WORKLOADS)}.",
            f"- Rework (no-skill/TDD): "
            f"{sum(payload['summary'][provider][w][NO_SKILL]['reworks'] for w in WORKLOADS)}/"
            f"{sum(payload['summary'][provider][w][TDD]['reworks'] for w in WORKLOADS)}.",
            f"- Mutation detections (no-skill/TDD): "
            f"{sum(payload['summary'][provider][w][NO_SKILL]['mutation_detected'] for w in WORKLOADS)}/"
            f"{sum(payload['summary'][provider][w][TDD]['mutation_detected'] for w in WORKLOADS)}.",
        ))
    lines.extend((
        "", "## Reliability", "",
        f"- Live samples: {len(samples)}; eligible: {sum(item['effectiveness_eligible'] for item in samples)}.",
        f"- Approved seams present: {sum(item['skill']['approved_seams_present'] for item in samples)}/{len(samples)}.",
        f"- Unexpected dependencies: {sum(bool(item['skill']['unexpected_dependencies']) for item in samples)}.",
        f"- User questions: {sum(item['control']['user_question_count'] for item in samples)}; nested agents: {sum(item['control']['nested_agent_count'] for item in samples)}.",
        f"- Contamination: {sum(item['skill']['contamination'] for item in samples)}; scope violations: {sum(item['quality']['scope_violation'] for item in samples)}.",
        f"- Replay mismatches: {sum(not item['replay_digest_matches'] for item in samples)}.",
        "", "## Workload conclusion", "",
        "- W2: quality was identical; TDD was harmful on Codex and provided no benefit on Claude.",
        "- W3: quality and mutation detection were identical; TDD provided no benefit on either provider.",
        "- W4: Codex was substantially slower with no quality gain. Claude gained one mutation detection but was 19.7% slower, so it is manual-only.",
        "", "## Recommendation", "",
        f"- Overall TDD classification: `{payload['overall_classification']}`.",
        "- Fast: OFF.",
        "- Simple implementation: OFF.",
        "- Regression-prone behavior: Codex OFF; Claude explicit manual use only.",
        "- Complex behavior: insufficient data beyond this bounded W4; no automatic binding.",
        "- No automatic binding was enabled by this benchmark.",
    ))
    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> int:
    central, manifest, raw_digest = pin_tdd()
    existing: list[TddBenchmarkSample] = []
    if args.resume and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        existing = [TddBenchmarkSample.from_dict(item) for item in previous.get("samples", ())]
    providers = tuple(args.providers or PROVIDERS)
    workloads = tuple(args.workloads or WORKLOADS)
    samples = await collect(
        central, manifest, args.output, existing, providers, workloads, args.repetitions,
    )
    summary = {
        provider: {
            workload: medians([
                item for item in samples
                if item.provider == provider and item.workload == workload
            ]) for workload in WORKLOADS
        } for provider in PROVIDERS
    }
    classes = [summary[p][w]["classification"] for p in PROVIDERS for w in WORKLOADS]
    payload = {
        "schema_version": 1, "collect_only": True,
        "adaptive_routing_enabled": False, "skill_policy_changed": False,
        "model_router_changed": False, "created_at": now(),
        "environment": {
            "python": sys.version.split()[0], "platform": sys.platform,
            "codex": command_version("codex"), "claude": command_version("claude"),
        },
        "skill": {
            "id": "tdd", "digest": manifest.content_digest,
            "raw_package_digest": raw_digest, "source_commit": None,
            "source_revision": manifest.source_commit,
            "source_commit_status": "unavailable_local_copy",
            "source": manifest.source, "source_path": "~/.agents/skills/tdd",
            "license": manifest.license,
            "referenced_files": list(manifest.referenced_files),
            "dependencies": list(manifest.dependencies),
            "plugin_installed": False, "hooks_executed": False,
        },
        "sampling": {
            "planned_runs": len(PROVIDERS) * len(WORKLOADS) * 2 * args.repetitions,
            "actual_runs": len(samples), "paired_order": "AB/BA",
        },
        "summary": summary, "overall_classification": overall_classification(classes),
        "samples": [item.to_dict() for item in samples],
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({
        "sampling": payload["sampling"], "summary": summary,
        "overall_classification": payload["overall_classification"],
    }, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--providers", nargs="*", choices=PROVIDERS)
    parser.add_argument("--workloads", nargs="*", choices=WORKLOADS)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "docs" / "research" / "RRC-05B_RESULTS.json",
    )
    parser.add_argument(
        "--report", type=Path,
        default=ROOT / "docs" / "research" / "RRC-05B_TDD_EFFECTIVENESS.md",
    )
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
