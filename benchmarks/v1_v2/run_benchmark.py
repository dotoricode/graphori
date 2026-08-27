#!/usr/bin/env python3
"""Run a bounded, reproducible Graphori v1 versus v2 comparison."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable
import uuid


MODEL = "gpt-5.6-terra"
EFFORT = "medium"
SEED = 20260824
V1_COMMIT = "93c5fcf"


@dataclass(frozen=True)
class Workload:
    workload_id: str
    objective: str
    source: str
    visible_test: str
    hidden_test: str
    source_path: str
    visible_module: str
    hidden_module: str


WORKLOADS = (
    Workload(
        "normalize-tags",
        "Implement normalize_tags(values) in src/tags.py. It must trim surrounding "
        "whitespace, lowercase each tag, omit empty tags, remove duplicates while "
        "preserving first-seen order, accept any iterable, and raise TypeError when "
        "an item is not a string. Run exactly: python -m unittest tests.test_tags. "
        "Modify only src/tags.py.",
        """def normalize_tags(values):
    raise NotImplementedError
""",
        """import unittest
from src.tags import normalize_tags


class NormalizeTagsVisibleTest(unittest.TestCase):
    def test_normalizes_a_list(self):
        self.assertEqual(normalize_tags([" Alpha ", "BETA", "alpha", "  "]),
                         ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
""",
        """import unittest
from src.tags import normalize_tags


class NormalizeTagsHiddenTest(unittest.TestCase):
    def test_accepts_generator_and_preserves_order(self):
        values = (item for item in [" B ", "a", "b", " C"])
        self.assertEqual(normalize_tags(values), ["b", "a", "c"])

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            normalize_tags(["ok", 3])

    def test_empty_iterable(self):
        self.assertEqual(normalize_tags([]), [])


if __name__ == "__main__":
    unittest.main()
""",
        "src/tags.py",
        "tests.test_tags",
        "hidden_tests.test_tags_hidden",
    ),
    Workload(
        "config-parser",
        "Implement parse_config(text) in src/config.py. Parse a JSON object with "
        "required name (a non-empty string), optional retries (an integer from 0 "
        "through 5, default 0; bool is not an integer), and optional enabled "
        "(a bool, default True). Reject arrays, invalid JSON, missing or blank names, "
        "wrong types, out-of-range retries, and unknown keys by raising ValueError. "
        "Return a dict containing name, retries, and enabled. Run exactly: "
        "python -m unittest tests.test_config. Modify only src/config.py.",
        """def parse_config(text):
    raise NotImplementedError
""",
        """import unittest
from src.config import parse_config


class ParseConfigVisibleTest(unittest.TestCase):
    def test_full_config(self):
        self.assertEqual(parse_config('{"name":"demo","retries":2,"enabled":false}'),
                         {"name": "demo", "retries": 2, "enabled": False})

    def test_defaults(self):
        self.assertEqual(parse_config('{"name":"demo"}'),
                         {"name": "demo", "retries": 0, "enabled": True})


if __name__ == "__main__":
    unittest.main()
""",
        """import unittest
from src.config import parse_config


class ParseConfigHiddenTest(unittest.TestCase):
    def assert_invalid(self, text):
        with self.assertRaises(ValueError):
            parse_config(text)

    def test_rejects_bad_shapes_and_json(self):
        for value in ('[1]', '{', '{}', '{"name":"   "}'):
            with self.subTest(value=value):
                self.assert_invalid(value)

    def test_rejects_types_ranges_and_unknown_keys(self):
        values = (
            '{"name":"x","retries":true}',
            '{"name":"x","retries":-1}',
            '{"name":"x","retries":6}',
            '{"name":"x","enabled":1}',
            '{"name":"x","extra":1}',
        )
        for value in values:
            with self.subTest(value=value):
                self.assert_invalid(value)

    def test_accepts_boundaries(self):
        self.assertEqual(parse_config('{"name":"x","retries":0}')['retries'], 0)
        self.assertEqual(parse_config('{"name":"x","retries":5}')['retries'], 5)


if __name__ == "__main__":
    unittest.main()
""",
        "src/config.py",
        "tests.test_config",
        "hidden_tests.test_config_hidden",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_command(argv: list[str], *, cwd: Path, timeout: float = 60,
                env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
    )


def create_fixture(root: Path, workload: Workload) -> None:
    for directory in ("src", "tests", "hidden_tests"):
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory / "__init__.py").write_text("", encoding="utf-8")
    (root / workload.source_path).write_text(workload.source, encoding="utf-8")
    visible_name = workload.visible_module.rsplit(".", 1)[-1] + ".py"
    (root / "tests" / visible_name).write_text(workload.visible_test, encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"graphori-v1-v2-fixture\"\nversion = \"0.0.0\"\n"
        "requires-python = \">=3.11\"\n",
        encoding="utf-8",
    )
    run_command(["git", "init", "-q"], cwd=root)
    run_command(["git", "config", "user.email", "benchmark@example.invalid"], cwd=root)
    run_command(["git", "config", "user.name", "Graphori Benchmark"], cwd=root)
    run_command(["git", "add", "."], cwd=root)
    result = run_command(["git", "commit", "-qm", "benchmark fixture"], cwd=root)
    if result.returncode:
        raise RuntimeError(result.stderr)


def changed_paths(root: Path) -> tuple[str, ...]:
    result = run_command(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root,
    )
    return tuple(sorted(
        line[3:] for line in result.stdout.splitlines()
        if len(line) >= 4 and not line[3:].startswith(".graphori/")
    ))


def check(root: Path, module: str) -> dict[str, Any]:
    started = time.monotonic()
    result = run_command([sys.executable, "-m", "unittest", module], cwd=root)
    return {
        "passed": result.returncode == 0,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "exit_code": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def hidden_check(root: Path, workload: Workload) -> dict[str, Any]:
    """Materialize the hidden oracle only after the condition has finished."""
    hidden_name = workload.hidden_module.rsplit(".", 1)[-1] + ".py"
    path = root / "hidden_tests" / hidden_name
    path.write_text(workload.hidden_test, encoding="utf-8")
    try:
        return check(root, workload.hidden_module)
    finally:
        path.unlink(missing_ok=True)


def usage_from(metadata: dict[str, Any]) -> dict[str, int | None]:
    usage = metadata.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }


async def direct_agent_call(candidate: Path, root: Path, workload: Workload,
                            *, verifier: bool) -> dict[str, Any]:
    sys.path.insert(0, str(candidate / "src"))
    try:
        from graphori_adapters.codex.adapter import CodexExecutionAdapter
        from graphori_core import ContextBundle, NodeSpec, ProcessLimits, RunPlan
    finally:
        sys.path.pop(0)

    role = "verifier" if verifier else "implementer"
    node_id = f"v1-{role}-{uuid.uuid4().hex[:8]}"
    if verifier:
        objective = (
            "Independently verify the completed task below. Inspect the implementation, "
            f"run exactly `python -m unittest {workload.visible_module}`, and do not "
            "modify files. Return status=succeeded only when the stated requirements and "
            f"visible tests are satisfied. Task: {workload.objective}"
        )
        write_scope: tuple[str, ...] = ()
    else:
        objective = workload.objective
        write_scope = (workload.source_path,)
    read_scope = (workload.source_path, f"tests/{workload.visible_module.rsplit('.', 1)[-1]}.py")
    node = NodeSpec(
        node_id, "verification" if verifier else "implementation",
        f"v1 {role}", objective, "verifier" if verifier else "worker",
        role=role, read_scope=read_scope, write_scope=write_scope,
        provider="codex", provider_family="openai", adapter="codex",
        model=MODEL, model_family="terra", effort=EFFORT,
        task_kind="verification" if verifier else "bounded_implementation",
        verification_policy="independent",
    )
    adapter = CodexExecutionAdapter(
        workspace_root=root,
        limits=ProcessLimits(timeout_seconds=240, grace_seconds=3),
    )
    capabilities = adapter.probe()
    if not capabilities.available:
        raise RuntimeError(capabilities.reason)
    plan = RunPlan(f"v1-{uuid.uuid4().hex}", 1, "committed", nodes=(node,))
    await adapter.prepare_run(plan)
    session = await adapter.start_session(node)
    context = ContextBundle(
        objective=objective,
        attempt_id=f"attempt:{node_id}:1",
        acceptance_criteria=(workload.objective,),
        read_scope=read_scope,
        write_scope=write_scope,
    )
    dispatch = await adapter.dispatch(session, node, context)
    async for _ in adapter.events(dispatch):
        pass
    result = await adapter.collect(dispatch)
    await adapter.release(session)
    metadata = dict(result.runtime_metadata)
    return {
        "outcome": result.outcome,
        "status": metadata.get("worker_report_status", "unknown"),
        "summary": result.summary,
        "files_modified": list(result.files_modified),
        "elapsed_ms": result.total_attempt_ms,
        "usage": usage_from(metadata),
        "error_kind": result.error_kind,
    }


async def run_v1(candidate: Path, root: Path, workload: Workload) -> dict[str, Any]:
    started = time.monotonic()
    worker = await direct_agent_call(candidate, root, workload, verifier=False)
    verifier = await direct_agent_call(candidate, root, workload, verifier=True)
    visible = check(root, workload.visible_module)
    paths = changed_paths(root)
    hidden = hidden_check(root, workload)
    claim = worker["status"] == "succeeded" and verifier["status"] == "succeeded"
    return {
        "condition": "v1-reconstructed",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "provider_calls": 2,
        "worker": worker,
        "condition_verifier": verifier,
        "visible_check": visible,
        "hidden_judge": hidden,
        "changed_paths": list(paths),
        "scope_violation": bool(set(paths) - {workload.source_path}),
        "completion_claim": claim,
        "claim_matches_hidden_judge": claim == hidden["passed"],
    }


def parse_journal(root: Path, run_id: str) -> dict[str, Any]:
    path = root / ".graphori" / "runs" / run_id / "journal" / "journal.jsonl"
    events = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    worker_status = "unknown"
    worker_elapsed_ms = None
    for event in events:
        payload = event.get("payload") or {}
        metadata = payload.get("runtime_metadata") or {}
        raw_usage = metadata.get("usage") or {}
        for key in usage:
            value = raw_usage.get(key)
            if isinstance(value, int):
                usage[key] += value
        if event.get("type") == "worker_finished" and event.get("actor", {}).get("role") == "worker":
            worker_status = metadata.get("worker_report_status", payload.get("outcome", "unknown"))
            worker_elapsed_ms = payload.get("total_attempt_ms")
    return {
        "path": str(path),
        "event_count": len(events),
        "usage": usage,
        "worker_status": worker_status,
        "worker_elapsed_ms": worker_elapsed_ms,
    }


def extract_last_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        # Product JSON is pretty-printed at column zero. Nested objects are
        # indented, so accepting every ``{`` would make the final nested object
        # look like the command result.
        if not line.startswith("{"):
            offset += len(line)
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            offset += len(line)
            continue
        if isinstance(value, dict):
            candidates.append(value)
        offset += len(line)
    return candidates[-1] if candidates else {}


async def run_v2(candidate: Path, root: Path, workload: Workload) -> dict[str, Any]:
    run_id = f"benchmark-v2-{workload.workload_id}-{uuid.uuid4().hex[:10]}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(candidate / "src")
    visible_path = f"tests/{workload.visible_module.rsplit('.', 1)[-1]}.py"
    argv = [
        sys.executable, "-m", "graphori_core.product_cli", "run", workload.objective,
        "--root", str(root), "--run-id", run_id, "--max-parallelism", "1",
        "--read-scope", workload.source_path, "--read-scope", visible_path,
        "--write-scope", workload.source_path,
        "--timeout", "240", "--criterion", f"AC-01:{workload.objective}",
        "--json", "--locale", "en", "--verify-command",
        sys.executable, "-m", "unittest", workload.visible_module,
    ]
    started = time.monotonic()
    process = await asyncio.to_thread(
        run_command, argv, cwd=root, timeout=300, env=env,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    product_result = extract_last_json(process.stdout)
    journal = parse_journal(root, run_id)
    visible = check(root, workload.visible_module)
    paths = changed_paths(root)
    hidden = hidden_check(root, workload)
    terminal = product_result.get("terminal_status", "unknown")
    claim = process.returncode == 0 and terminal == "succeeded"
    return {
        "condition": "v2-candidate",
        "elapsed_ms": elapsed_ms,
        "provider_calls": 1,
        "exit_code": process.returncode,
        "terminal_status": terminal,
        "worker": {"status": journal["worker_status"], "usage": journal["usage"]},
        "journal": journal,
        "visible_check": visible,
        "hidden_judge": hidden,
        "changed_paths": list(paths),
        "scope_violation": bool(set(paths) - {workload.source_path}),
        "completion_claim": claim,
        "claim_matches_hidden_judge": claim == hidden["passed"],
        "stdout_tail": process.stdout[-3000:],
        "stderr_tail": process.stderr[-3000:],
    }


def content_digest(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    paths = tuple(paths)
    common = Path(os.path.commonpath(paths)) if paths else Path(".")
    for path in sorted(paths):
        digest.update(str(path.relative_to(common)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def candidate_digest(candidate: Path) -> str:
    paths = list((candidate / "src").rglob("*.py"))
    paths.extend((candidate / "graphori").rglob("*.md"))
    return content_digest(paths)


def command_version(argv: list[str]) -> str:
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False, timeout=15)
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unavailable"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for condition in ("v1-reconstructed", "v2-candidate"):
        selected = [row for row in rows if row["condition"] == condition]
        tokens = []
        for row in selected:
            calls = [row["worker"]]
            if condition == "v1-reconstructed":
                calls.append(row["condition_verifier"])
            tokens.append({
                key: sum((call.get("usage") or {}).get(key) or 0 for call in calls)
                for key in ("input_tokens", "cached_input_tokens", "output_tokens")
            })
        result[condition] = {
            "runs": len(selected),
            "hidden_judge_passes": sum(row["hidden_judge"]["passed"] for row in selected),
            "visible_check_passes": sum(row["visible_check"]["passed"] for row in selected),
            "scope_violations": sum(row["scope_violation"] for row in selected),
            "claim_matches": sum(row["claim_matches_hidden_judge"] for row in selected),
            "provider_calls": sum(row["provider_calls"] for row in selected),
            "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in selected)),
            "total_input_tokens": sum(item["input_tokens"] for item in tokens),
            "total_cached_input_tokens": sum(item["cached_input_tokens"] for item in tokens),
            "total_output_tokens": sum(item["output_tokens"] for item in tokens),
        }
    return result


async def main_async(args: argparse.Namespace) -> int:
    candidate = args.v2_source.resolve()
    if not (candidate / "src/graphori_core/product_cli.py").is_file():
        raise SystemExit(f"v2 source is missing product_cli.py: {candidate}")
    order = [
        (workload, condition, repetition)
        for workload in WORKLOADS
        for condition in ("v1", "v2")
        for repetition in range(1, args.repetitions + 1)
    ]
    random.Random(args.seed).shuffle(order)
    rows: list[dict[str, Any]] = []
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    with tempfile.TemporaryDirectory(prefix="graphori-v1-v2-") as temp:
        temp_root = Path(temp)
        for index, (workload, condition, repetition) in enumerate(order, 1):
            fixture = temp_root / f"{index:02d}-{condition}-{workload.workload_id}-r{repetition}"
            fixture.mkdir()
            create_fixture(fixture, workload)
            print(
                f"[{index}/{len(order)}] {condition} {workload.workload_id} "
                f"repetition={repetition}", flush=True,
            )
            try:
                row = (
                    await run_v1(candidate, fixture, workload)
                    if condition == "v1"
                    else await run_v2(candidate, fixture, workload)
                )
                row.update({
                    "workload_id": workload.workload_id,
                    "repetition": repetition,
                    "execution_index": index,
                })
            except Exception as exc:
                row = {
                    "condition": "v1-reconstructed" if condition == "v1" else "v2-candidate",
                    "workload_id": workload.workload_id,
                    "repetition": repetition,
                    "execution_index": index,
                    "infrastructure_error": type(exc).__name__,
                    "error_detail": str(exc)[:1000],
                    "elapsed_ms": 0,
                    "provider_calls": 0,
                    "worker": {"usage": {}},
                    "condition_verifier": {"usage": {}},
                    "visible_check": {"passed": False},
                    "hidden_judge": {"passed": False},
                    "scope_violation": False,
                    "claim_matches_hidden_judge": False,
                }
            rows.append(row)
            partial = {
                "schema_version": 1,
                "status": "running",
                "started_at": started_at,
                "environment": {
                    "v1_commit": V1_COMMIT,
                    "v2_source": "<v2-source>",
                    "v2_source_digest": candidate_digest(candidate),
                    "codex_cli": command_version(["codex", "--version"]),
                    "python": sys.version.split()[0],
                    "model": MODEL,
                    "effort": EFFORT,
                    "seed": args.seed,
                    "repetitions": args.repetitions,
                },
                "rows": rows,
            }
            output.write_text(json.dumps(partial, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    result = {
        "schema_version": 1,
        "status": "complete",
        "started_at": started_at,
        "finished_at": utc_now(),
        "environment": partial["environment"],
        "execution_order": [
            {"workload_id": w.workload_id, "condition": c, "repetition": r}
            for w, c, r in order
        ],
        "rows": rows,
        "summary": summarize(rows),
    }
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/v1_v2/results.json"))
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--seed", type=int, default=SEED)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.repetitions < 2:
        raise SystemExit("repetitions must be at least 2")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
