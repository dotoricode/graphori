#!/usr/bin/env python3
"""Run the public Direct/v1-style/Graphori v2 benchmark without inventing data."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping
import uuid


SEED = 20260828
PROVIDERS = ("codex", "claude")
ARMS = ("direct", "v1-style", "graphori-v2")
MODELS = (
    "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
    "claude-sonnet-5", "claude-opus-5",
)


@dataclass(frozen=True)
class Workload:
    task_id: str
    category: str
    objective: str
    sources: Mapping[str, str]
    visible_path: str
    visible_module: str
    visible_test: str
    hidden_path: str
    hidden_module: str
    hidden_test: str
    hidden_tests_total: int
    write_scope: tuple[str, ...]

    @property
    def read_scope(self) -> tuple[str, ...]:
        return tuple(sorted((*self.sources, self.visible_path)))


WORKLOADS = (
    Workload(
        "normalize-tags", "small-fix",
        "Implement normalize_tags(values) in src/tags.py. Trim surrounding whitespace, "
        "lowercase each tag, omit empty tags, remove duplicates while preserving first-seen "
        "order, accept any iterable, and raise TypeError when an item is not a string. Run "
        "exactly `python -m unittest tests.test_tags`. Modify only src/tags.py.",
        {"src/tags.py": "def normalize_tags(values):\n    raise NotImplementedError\n"},
        "tests/test_tags.py", "tests.test_tags",
        """import unittest
from src.tags import normalize_tags

class Visible(unittest.TestCase):
    def test_normalizes(self):
        self.assertEqual(normalize_tags([" Alpha ", "BETA", "alpha", "  "]),
                         ["alpha", "beta"])
""",
        "hidden_tests/test_tags_hidden.py", "hidden_tests.test_tags_hidden",
        """import unittest
from src.tags import normalize_tags

class Hidden(unittest.TestCase):
    def test_generator_and_order(self):
        self.assertEqual(normalize_tags(x for x in [" B ", "a", "b", " C"]),
                         ["b", "a", "c"])
    def test_non_string(self):
        with self.assertRaises(TypeError): normalize_tags(["ok", 3])
    def test_empty(self):
        self.assertEqual(normalize_tags([]), [])
""", 3, ("src/tags.py",),
    ),
    Workload(
        "config-parser", "bounded-feature",
        "Implement parse_config(text) in src/config.py. Parse a JSON object with required "
        "name (a non-empty string), optional retries (an integer from 0 through 5, default 0; "
        "bool is not an integer), and optional enabled (a bool, default True). Reject arrays, "
        "invalid JSON, missing or blank names, wrong types, out-of-range retries, and unknown "
        "keys by raising ValueError. Return a dict containing name, retries, and enabled. Run "
        "exactly `python -m unittest tests.test_config`. Modify only src/config.py.",
        {"src/config.py": "def parse_config(text):\n    raise NotImplementedError\n"},
        "tests/test_config.py", "tests.test_config",
        """import unittest
from src.config import parse_config

class Visible(unittest.TestCase):
    def test_full(self):
        self.assertEqual(parse_config('{"name":"demo","retries":2,"enabled":false}'),
                         {"name": "demo", "retries": 2, "enabled": False})
    def test_defaults(self):
        self.assertEqual(parse_config('{"name":"demo"}'),
                         {"name": "demo", "retries": 0, "enabled": True})
""",
        "hidden_tests/test_config_hidden.py", "hidden_tests.test_config_hidden",
        """import unittest
from src.config import parse_config

class Hidden(unittest.TestCase):
    def assert_invalid(self, value):
        with self.assertRaises(ValueError): parse_config(value)
    def test_shapes_and_json(self):
        for value in ('[1]', '{', '{}', '{"name":"   "}'):
            with self.subTest(value=value): self.assert_invalid(value)
    def test_types_ranges_unknown(self):
        for value in ('{"name":"x","retries":true}', '{"name":"x","retries":-1}',
                      '{"name":"x","retries":6}', '{"name":"x","enabled":1}',
                      '{"name":"x","extra":1}'):
            with self.subTest(value=value): self.assert_invalid(value)
    def test_boundaries(self):
        self.assertEqual(parse_config('{"name":"x","retries":0}')["retries"], 0)
        self.assertEqual(parse_config('{"name":"x","retries":5}')["retries"], 5)
""", 3, ("src/config.py",),
    ),
    Workload(
        "retry-policy", "multi-file-feature",
        "Implement the retry policy in src/retry.py and src/errors.py. Define RetryExhausted "
        "as an Exception subclass with attempts and last_error attributes. Implement "
        "next_delay(attempt, base=0.5, maximum=8.0): attempt is a non-bool integer >= 1, base "
        "and maximum are positive numbers, base must not exceed maximum, and the result is "
        "min(maximum, base * 2 ** (attempt - 1)). Invalid input raises ValueError. Implement "
        "raise_if_exhausted(attempt, limit, error): limit is a positive non-bool integer; when "
        "attempt >= limit raise RetryExhausted(attempt, error), otherwise return None. Run "
        "exactly `python -m unittest tests.test_retry`. Modify only src/retry.py and "
        "src/errors.py.",
        {
            "src/retry.py": "def next_delay(attempt, base=0.5, maximum=8.0):\n    raise NotImplementedError\n\ndef raise_if_exhausted(attempt, limit, error):\n    raise NotImplementedError\n",
            "src/errors.py": "class RetryExhausted(Exception):\n    pass\n",
        },
        "tests/test_retry.py", "tests.test_retry",
        """import unittest
from src.errors import RetryExhausted
from src.retry import next_delay, raise_if_exhausted

class Visible(unittest.TestCase):
    def test_backoff_and_cap(self):
        self.assertEqual([next_delay(x) for x in (1, 2, 6)], [0.5, 1.0, 8.0])
    def test_exhaustion(self):
        with self.assertRaises(RetryExhausted): raise_if_exhausted(3, 3, ValueError("x"))
""",
        "hidden_tests/test_retry_hidden.py", "hidden_tests.test_retry_hidden",
        """import unittest
from src.errors import RetryExhausted
from src.retry import next_delay, raise_if_exhausted

class Hidden(unittest.TestCase):
    def test_validation(self):
        for args in ((True,), (0,), (1, 0), (1, 2, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError): next_delay(*args)
    def test_custom_and_no_raise(self):
        self.assertEqual(next_delay(3, 1.0, 10.0), 4.0)
        self.assertIsNone(raise_if_exhausted(2, 3, RuntimeError("x")))
        with self.assertRaises(ValueError): raise_if_exhausted(1, True, RuntimeError("x"))
    def test_exception_fields(self):
        error = RuntimeError("boom")
        try: raise_if_exhausted(4, 3, error)
        except RetryExhausted as exc:
            self.assertEqual(exc.attempts, 4)
            self.assertIs(exc.last_error, error)
        else: self.fail("RetryExhausted was not raised")
""", 3, ("src/errors.py", "src/retry.py"),
    ),
    Workload(
        "dependency-order", "boundary-bug-fix",
        "Fix topological_order(graph) in src/dependency.py. graph maps a node to an iterable "
        "of dependencies. Return every node, including dependency-only nodes, in a stable "
        "topological order; when several nodes are ready choose lexical order. Do not mutate "
        "the input. Reject a string as a dependency iterable with TypeError. Raise ValueError "
        "for cycles, including self-cycles. Run exactly `python -m unittest "
        "tests.test_dependency`. Modify only src/dependency.py.",
        {"src/dependency.py": """def topological_order(graph):
    # BUG: dependency-only nodes disappear and cycles return partial output.
    remaining = {node: set(deps) for node, deps in graph.items()}
    result = []
    while remaining:
        ready = [node for node, deps in remaining.items() if not deps]
        if not ready:
            return result
        node = ready[0]
        result.append(node)
        del remaining[node]
        for deps in remaining.values():
            deps.discard(node)
    return result
"""},
        "tests/test_dependency.py", "tests.test_dependency",
        """import unittest
from src.dependency import topological_order

class Visible(unittest.TestCase):
    def test_order(self):
        self.assertEqual(topological_order({"build": ["lint", "test"], "test": []}),
                         ["lint", "test", "build"])
""",
        "hidden_tests/test_dependency_hidden.py", "hidden_tests.test_dependency_hidden",
        """import unittest
from src.dependency import topological_order

class Hidden(unittest.TestCase):
    def test_stable_and_input_unchanged(self):
        graph = {"c": {"a"}, "b": set()}
        before = {key: set(value) for key, value in graph.items()}
        self.assertEqual(topological_order(graph), ["a", "b", "c"])
        self.assertEqual(graph, before)
    def test_cycles(self):
        for graph in ({"a": ["a"]}, {"a": ["b"], "b": ["a"]}):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                topological_order(graph)
    def test_string_dependencies(self):
        with self.assertRaises(TypeError): topological_order({"a": "bc"})
""", 3, ("src/dependency.py",),
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command_version(command: str) -> str:
    result = subprocess.run(
        [command, "--version"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=15, check=False,
    )
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unavailable"


def run_command(argv: list[str], *, cwd: Path, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )


def create_fixture(root: Path, workload: Workload) -> None:
    for package in ("src", "tests", "hidden_tests"):
        (root / package).mkdir(parents=True, exist_ok=True)
        (root / package / "__init__.py").write_text("", encoding="utf-8")
    for relative, content in workload.sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    visible = root / workload.visible_path
    visible.parent.mkdir(parents=True, exist_ok=True)
    visible.write_text(workload.visible_test, encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.graphori/\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname='graphori-three-arm-fixture'\nversion='0.0.0'\nrequires-python='>=3.11'\n",
        encoding="utf-8",
    )
    run_command(["git", "init", "-q"], cwd=root)
    run_command(["git", "config", "user.name", "Graphori Benchmark"], cwd=root)
    run_command(["git", "config", "user.email", "benchmark@example.invalid"], cwd=root)
    run_command(["git", "add", "."], cwd=root)
    committed = run_command(["git", "commit", "-qm", "benchmark fixture"], cwd=root)
    if committed.returncode:
        raise RuntimeError("fixture commit failed")


def changed_paths(root: Path) -> tuple[str, ...]:
    result = run_command(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root)
    return tuple(sorted(
        line[3:] for line in result.stdout.splitlines()
        if len(line) >= 4 and not line[3:].startswith(".graphori/")
    ))


def test_module(root: Path, module: str) -> dict[str, Any]:
    result = run_command([sys.executable, "-m", "unittest", module], cwd=root)
    return {
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
    }


def hidden_check(root: Path, workload: Workload) -> dict[str, Any]:
    path = root / workload.hidden_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workload.hidden_test, encoding="utf-8")
    try:
        return test_module(root, workload.hidden_module)
    finally:
        path.unlink(missing_ok=True)


def availability_for(provider: str):
    from graphori_core.model_routing import Availability
    return {
        model: Availability.AVAILABLE
        if (model.startswith("gpt-") if provider == "codex" else model.startswith("claude-"))
        else Availability.UNAVAILABLE
        for model in MODELS
    }


def compile_bundle(root: Path, workload: Workload, provider: str, run_id: str):
    from graphori_core.product import ProductPlanCompiler
    from graphori_core.run_spec import RunConstraints, RunSpec
    spec = RunSpec(
        workload.objective, "public-benchmark", str(root),
        constraints=RunConstraints(max_parallelism=1, allow_network=False),
        runtime_preference=(provider, "generic_process"),
        acceptance_criteria=(f"AC-01: {workload.objective}",),
    )
    bundle = ProductPlanCompiler(availability=availability_for(provider)).compile(
        spec, run_id=run_id, read_scope=workload.read_scope,
        write_scope=workload.write_scope,
        verification_argv=(sys.executable, "-m", "unittest", workload.visible_module),
    )
    worker = next(node for node in bundle.plan.nodes if node.node_id == "i1")
    if worker.provider != provider or worker.adapter != provider:
        raise RuntimeError(f"plan routed {provider} cell to {worker.provider}/{worker.adapter}")
    if worker.approval_required:
        raise RuntimeError("public benchmark unexpectedly selected a premium-gated model")
    return spec, bundle, worker


def make_adapter(provider: str, root: Path, timeout: int):
    from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter
    from graphori_adapters.codex.adapter import CodexExecutionAdapter
    from graphori_core import ProcessLimits
    cls = CodexExecutionAdapter if provider == "codex" else ClaudeCodeExecutionAdapter
    adapter = cls(workspace_root=root, limits=ProcessLimits(timeout_seconds=timeout, grace_seconds=3))
    probe = adapter.probe()
    if not probe.available:
        raise RuntimeError(f"{provider} unavailable: {probe.reason}")
    return adapter


def normalize_usage(metadata: Mapping[str, Any]) -> dict[str, int | float | None]:
    raw = metadata.get("usage") if isinstance(metadata.get("usage"), Mapping) else {}
    provider = metadata.get("provider")
    output = raw.get("output_tokens") if isinstance(raw.get("output_tokens"), int) else None
    if provider == "claude":
        base = raw.get("input_tokens")
        created = raw.get("cache_creation_input_tokens", 0)
        cached = raw.get("cache_read_input_tokens", 0)
        if not all(isinstance(item, int) for item in (base, created, cached)):
            total = fresh = cached_value = None
        else:
            fresh = base + created
            cached_value = cached
            total = fresh + cached_value
    else:
        total = raw.get("input_tokens") if isinstance(raw.get("input_tokens"), int) else None
        cached_value = raw.get("cached_input_tokens") if isinstance(raw.get("cached_input_tokens"), int) else None
        fresh = total - cached_value if total is not None and cached_value is not None else None
    cost = metadata.get("provider_reported_cost_usd")
    return {
        "total_input_tokens": total,
        "cached_input_tokens": cached_value,
        "fresh_input_tokens": fresh,
        "output_tokens": output,
        "cost_usd": float(cost) if isinstance(cost, (int, float)) else None,
    }


def sum_known(calls: list[Mapping[str, Any]], key: str):
    values = [call.get(key) for call in calls]
    return sum(values) if values and all(isinstance(value, (int, float)) for value in values) else None


async def agent_call(adapter, node, objective: str, workload: Workload) -> dict[str, Any]:
    from graphori_core import ContextBundle, RunPlan
    await adapter.prepare_run(RunPlan(f"call-{uuid.uuid4().hex}", 1, "committed", nodes=(node,)))
    session = await adapter.start_session(node)
    context = ContextBundle(
        objective=objective, attempt_id=f"attempt:{node.node_id}:1",
        acceptance_criteria=(f"AC-01: {workload.objective}",),
        read_scope=node.read_scope, write_scope=node.write_scope,
    )
    dispatch = await adapter.dispatch(session, node, context)
    try:
        async for _event in adapter.events(dispatch):
            pass
        result = await adapter.collect(dispatch)
    finally:
        await adapter.release(session)
    metadata = dict(result.runtime_metadata)
    return {
        "outcome": result.outcome,
        "report_status": metadata.get("worker_report_status", "missing"),
        "usage": normalize_usage(metadata),
        "elapsed_ms": result.total_attempt_ms,
        "exit_code": result.exit_code,
        "stdout_digest": result.stdout_digest,
        "stderr_digest": result.stderr_digest,
        "observed_model": metadata.get("observed_model", ""),
        "requested_model": metadata.get("requested_model", ""),
        "files_modified": list(result.files_modified),
    }


async def run_direct(root: Path, workload: Workload, provider: str, timeout: int):
    _spec, _bundle, worker = compile_bundle(root, workload, provider, f"plan-{uuid.uuid4().hex}")
    adapter = make_adapter(provider, root, timeout)
    result = await agent_call(adapter, worker, workload.objective, workload)
    return [result], result["report_status"] == "succeeded", 0, worker


async def run_v1_style(root: Path, workload: Workload, provider: str, timeout: int):
    _spec, _bundle, worker = compile_bundle(root, workload, provider, f"plan-{uuid.uuid4().hex}")
    implementation = await agent_call(make_adapter(provider, root, timeout), worker,
                                      workload.objective, workload)
    verifier_objective = (
        "Independently review the completed task. Inspect the implementation, run exactly "
        f"`python -m unittest {workload.visible_module}`, do not modify files, and report "
        f"succeeded only when the requirements and visible tests are satisfied. Task: "
        f"{workload.objective}"
    )
    verifier = replace(
        worker, node_id="review", team_id="verification", title="Independent AI review",
        objective=verifier_objective, kind="verifier", role="verifier",
        write_scope=(), permission_profile="read_only", dependencies=(),
        task_kind="verification", verification_policy="independent",
    )
    review = await agent_call(make_adapter(provider, root, timeout), verifier,
                              verifier_objective, workload)
    claim = implementation["report_status"] == "succeeded" and review["report_status"] == "succeeded"
    return [implementation, review], claim, 0, worker


def journal_worker_calls(root: Path, run_id: str) -> tuple[list[dict[str, Any]], int]:
    path = root / ".graphori" / "runs" / run_id / "journal" / "journal.jsonl"
    calls: list[dict[str, Any]] = []
    reworks = 0
    if not path.is_file():
        return calls, reworks
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") in {"graph_revised", "rework_created"}:
            reworks += 1
        if event.get("type") != "worker_finished" or (event.get("actor") or {}).get("role") != "worker":
            continue
        payload = event.get("payload") or {}
        metadata = payload.get("runtime_metadata") or {}
        calls.append({
            "outcome": payload.get("outcome", "unknown"),
            "report_status": metadata.get("worker_report_status", "missing"),
            "usage": normalize_usage(metadata),
            "elapsed_ms": payload.get("total_attempt_ms"),
            "exit_code": payload.get("exit_code"),
            "stdout_digest": payload.get("stdout_digest", ""),
            "stderr_digest": payload.get("stderr_digest", ""),
            "observed_model": metadata.get("observed_model", ""),
            "requested_model": metadata.get("requested_model", ""),
            "files_modified": payload.get("files_modified", []),
        })
    return calls, reworks


async def run_graphori_v2(root: Path, workload: Workload, provider: str, timeout: int):
    from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter
    from graphori_adapters.codex.adapter import CodexExecutionAdapter
    from graphori_adapters.direct import RoutedExecutionAdapter
    from graphori_adapters.generic.adapter import GenericProcessAdapter, ProcessCommand
    from graphori_core import GraphExecutionEngine, ProcessLimits
    from graphori_core.product import execute_product

    run_id = f"benchmark-{provider}-{workload.task_id}-{uuid.uuid4().hex[:12]}"
    spec, bundle, worker = compile_bundle(root, workload, provider, run_id)
    limits = ProcessLimits(timeout_seconds=timeout, grace_seconds=3)
    codex = CodexExecutionAdapter(workspace_root=root, limits=limits)
    claude = ClaudeCodeExecutionAdapter(workspace_root=root, limits=limits)
    commands = {
        node_id: ProcessCommand(
            command.argv, verdict_file=command.verdict_file,
            env={"PYTHONDONTWRITEBYTECODE": "1"}, limits=limits,
        ) for node_id, command in bundle.process_commands.items()
    }
    generic = GenericProcessAdapter(workspace_root=root, commands=commands, max_concurrency=1)
    routed = RoutedExecutionAdapter({"codex": codex, "claude": claude, "generic-process": generic})
    engine = GraphExecutionEngine(adapter=routed, plan_factory=lambda _spec: bundle.plan)
    projection = await execute_product(engine, spec, bundle.plan)
    calls, reworks = journal_worker_calls(root, run_id)
    return calls, projection.terminal_status == "succeeded", reworks, worker


def source_commit(root: Path) -> str:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=root)
    if result.returncode:
        raise RuntimeError("benchmark source commit is unavailable")
    return result.stdout.strip()


def aggregate_usage(calls: list[Mapping[str, Any]]) -> dict[str, int | float | None]:
    usage = [call.get("usage") or {} for call in calls]
    return {
        "ai_sessions": len(calls),
        "total_input_tokens": sum_known(usage, "total_input_tokens"),
        "cached_input_tokens": sum_known(usage, "cached_input_tokens"),
        "fresh_input_tokens": sum_known(usage, "fresh_input_tokens"),
        "output_tokens": sum_known(usage, "output_tokens"),
        "cost_usd": sum_known(usage, "cost_usd"),
    }


async def run_cell(candidate: Path, workload: Workload, provider: str, arm: str,
                   repetition: int, timeout: int, execution_index: int) -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="graphori-three-arm-") as directory:
        root = Path(directory)
        create_fixture(root, workload)
        try:
            if arm == "direct":
                calls, claim, reworks, worker = await run_direct(root, workload, provider, timeout)
            elif arm == "v1-style":
                calls, claim, reworks, worker = await run_v1_style(root, workload, provider, timeout)
            else:
                calls, claim, reworks, worker = await run_graphori_v2(root, workload, provider, timeout)
            visible = test_module(root, workload.visible_module)
            hidden = hidden_check(root, workload)
            paths = changed_paths(root)
            violations = sorted(set(paths) - set(workload.write_scope))
            elapsed = time.monotonic() - started
            succeeded = visible["passed"] and hidden["passed"] and not violations
            evidence_text = json.dumps({
                "calls": [{key: call.get(key) for key in (
                    "outcome", "report_status", "exit_code", "stdout_digest", "stderr_digest",
                    "requested_model", "observed_model", "files_modified",
                )} for call in calls],
                "visible": visible, "hidden": hidden,
            }, sort_keys=True).encode()
            return {
                "schema_version": 2,
                "run_id": f"{provider}-{arm}-{workload.task_id}-r{repetition}-{uuid.uuid4().hex[:8]}",
                "arm": arm, "provider": provider, "repetition": repetition,
                "task_id": workload.task_id, "task_category": workload.category,
                "execution_index": execution_index,
                "started_at": started_at, "finished_at": utc_now(),
                "source_commit": source_commit(candidate),
                "model": worker.model, "effort": worker.effort,
                "provider_cli_version": command_version(provider),
                "command": ["python", "benchmarks/three_arm/run.py", "--provider", provider,
                            "--arm", arm, "--task", workload.task_id,
                            "--repetition", str(repetition)],
                "outcome": "succeeded" if succeeded else "failed",
                "usage": aggregate_usage(calls),
                "quality": {
                    "hidden_tests_passed": workload.hidden_tests_total if hidden["passed"] else 0,
                    "hidden_tests_total": workload.hidden_tests_total,
                    "ttur_seconds": round(elapsed, 3), "rework_count": reworks,
                    "scope_violations": len(violations),
                },
                "evidence": {
                    "exit_code": 0 if succeeded else 1,
                    "stdout_sha256": hashlib.sha256(evidence_text).hexdigest(),
                    "stderr_sha256": hidden["stderr_sha256"],
                },
                "claim_matches_hidden": claim == hidden["passed"],
                "completion_claim": claim,
                "changed_paths": list(paths), "scope_violation_paths": violations,
            }
        except Exception as exc:
            return {
                "schema_version": 2,
                "run_id": f"{provider}-{arm}-{workload.task_id}-r{repetition}-{uuid.uuid4().hex[:8]}",
                "arm": arm, "provider": provider, "repetition": repetition,
                "task_id": workload.task_id, "task_category": workload.category,
                "execution_index": execution_index,
                "started_at": started_at, "finished_at": utc_now(),
                "source_commit": source_commit(candidate),
                "model": "unknown", "effort": "unknown",
                "provider_cli_version": command_version(provider),
                "command": ["python", "benchmarks/three_arm/run.py", "--provider", provider,
                            "--arm", arm, "--task", workload.task_id,
                            "--repetition", str(repetition)],
                "outcome": "unknown",
                "usage": {key: None for key in (
                    "ai_sessions", "total_input_tokens", "cached_input_tokens",
                    "fresh_input_tokens", "output_tokens", "cost_usd",
                )},
                "quality": {"hidden_tests_passed": None,
                            "hidden_tests_total": workload.hidden_tests_total,
                            "ttur_seconds": round(time.monotonic() - started, 3),
                            "rework_count": None, "scope_violations": None},
                "evidence": {"exit_code": None,
                             "stdout_sha256": hashlib.sha256(type(exc).__name__.encode()).hexdigest(),
                             "stderr_sha256": hashlib.sha256(str(exc).encode()).hexdigest()},
                "claim_matches_hidden": None, "completion_claim": None,
                "changed_paths": [], "scope_violation_paths": [],
                "infrastructure_error": type(exc).__name__,
                "error_detail": "bounded runner failure; see the local command transcript",
            }


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL at line {number}") from exc
        if not isinstance(value, dict):
            raise SystemExit(f"record {number} is not an object")
        records.append(value)
    return records


def append_record(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def selected(values: Iterable[str], allowed: tuple[str, ...], name: str) -> tuple[str, ...]:
    result = tuple(dict.fromkeys(values))
    unknown = set(result) - set(allowed)
    if unknown:
        raise SystemExit(f"unknown {name}: {', '.join(sorted(unknown))}")
    return result


async def main_async(args: argparse.Namespace) -> int:
    candidate = args.source.resolve()
    if not (candidate / "src/graphori_core/product.py").is_file():
        raise SystemExit(f"Graphori source is missing: {candidate}")
    sys.path.insert(0, str(candidate / "src"))
    providers = selected(args.provider or PROVIDERS, PROVIDERS, "provider")
    arms = selected(args.arm or ARMS, ARMS, "arm")
    workload_by_id = {item.task_id: item for item in WORKLOADS}
    tasks = selected(args.task or tuple(workload_by_id), tuple(workload_by_id), "task")
    order = [
        (provider, arm, workload_by_id[task], repetition)
        for provider in providers for task in tasks for arm in arms
        for repetition in range(1, args.repetitions + 1)
    ]
    random.Random(args.seed).shuffle(order)
    existing = load_existing(args.output)
    completed = {
        (row["provider"], row["arm"], row["task_id"], row["repetition"])
        for row in existing
    }
    if len(completed) != len(existing):
        raise SystemExit("output contains duplicate benchmark cells")
    total = len(order)
    for execution_index, (provider, arm, workload, repetition) in enumerate(order, 1):
        key = (provider, arm, workload.task_id, repetition)
        if key in completed:
            print(f"[{execution_index}/{total}] skip completed {provider} {arm} {workload.task_id} r{repetition}", flush=True)
            continue
        print(f"[{execution_index}/{total}] {provider} {arm} {workload.task_id} r{repetition}", flush=True)
        record = await run_cell(candidate, workload, provider, arm, repetition,
                                args.timeout, execution_index)
        append_record(args.output, record)
        print(f"  -> {record['outcome']} ttur={record['quality']['ttur_seconds']}s", flush=True)
        if record["outcome"] == "unknown" and args.fail_fast:
            return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path,
                        default=Path("benchmarks/three_arm/raw-results.jsonl"))
    parser.add_argument("--provider", action="append", choices=PROVIDERS)
    parser.add_argument("--arm", action="append", choices=ARMS)
    parser.add_argument("--task", action="append", choices=tuple(item.task_id for item in WORKLOADS))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.repetitions < 1:
        raise SystemExit("repetitions must be positive")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
