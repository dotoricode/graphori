#!/usr/bin/env python3
"""PR11D's disposable, no-provider release-acceptance evidence harness.

It deliberately creates all run roots below a temporary directory.  The
script does not start Graphori from inside Graphori, invoke a paid provider,
or make a visual claim about the dashboard; those remain coordinator checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO = Path(__file__).resolve().parents[1]
def _run(argv: list[str], *, env: dict[str, str], cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True, timeout=60)


def _record(results: list[dict], name: str, result: subprocess.CompletedProcess[str], detail: str = "") -> None:
    results.append({
        "id": name,
        "exit_code": result.returncode,
        "evidence": detail or ((result.stdout + "\n" + result.stderr).strip()[-900:]),
    })


def _require(result: subprocess.CompletedProcess[str], condition: bool, reason: str) -> subprocess.CompletedProcess[str]:
    """Turn an unmet acceptance assertion into a visible harness failure."""
    if result.returncode == 0 and not condition:
        return subprocess.CompletedProcess(result.args, 1, result.stdout, result.stderr + "\n" + reason)
    return result


def _fake_engine_script() -> str:
    return textwrap.dedent("""
        import asyncio, json, sys
        from graphori_adapters.direct import RoutedExecutionAdapter
        from graphori_core import (AdapterCapabilities, DispatchHandle, ExecutionResult,
            GraphExecutionEngine, NodeSpec, RunPlan, RunSpec, RuntimeRunHandle, SessionHandle)
        class Fake:
            adapter_id = "acceptance-fake"
            def probe(self): return AdapterCapabilities("acceptance-fake", True)
            async def prepare_run(self, plan): return RuntimeRunHandle("acceptance-fake", "fake")
            async def start_session(self, node): return SessionHandle("acceptance-fake", node.node_id)
            async def dispatch(self, session, node, context): return DispatchHandle("acceptance-fake", node.node_id, node.node_id)
            async def events(self, dispatch):
                if False: yield None
            async def collect(self, dispatch): return ExecutionResult("succeeded", evidence_ids=("acceptance:fake",))
            async def acknowledge(self, event): pass
            async def cancel(self, dispatch, reason): pass
            async def release(self, session): pass
        async def main():
            plan = RunPlan("fake-run", 1, "committed", nodes=(NodeSpec(
                "n", "research", "Fake", "read", "worker", adapter="codex", provider="codex",
                verification_policy="deterministic"),))
            engine = GraphExecutionEngine(adapter=RoutedExecutionAdapter({"codex": Fake()}), plan_factory=lambda _: plan)
            handle = await engine.start(RunSpec("fake acceptance", "codex", sys.argv[1]))
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            assert snapshot.terminal_status == "succeeded", snapshot
            print(json.dumps({"terminal_status": snapshot.terminal_status,
                              "projection_digest": snapshot.projection_digest}))
        asyncio.run(main())
    """)


def main() -> int:
    parser = argparse.ArgumentParser(description="PR11D local release acceptance harness")
    parser.add_argument("--report", type=Path, required=True, help="Markdown evidence report destination")
    args = parser.parse_args()
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="graphori-pr11d-") as temporary:
        tmp = Path(temporary)
        source = tmp / "source"
        shutil.copytree(
            REPO,
            source,
            ignore=shutil.ignore_patterns(
                ".git", ".graphori", "__pycache__", "*.pyc", "*.egg-info",
            ),
        )
        legacy_fixture = source / "tests" / "fixtures" / "dashboard" / "legacy-pre-pr10.jsonl"
        environment = tmp / "venv"
        # The package contract is Python 3.11+.  Prefer the maintained 3.11
        # interpreter so the disposable environment includes its bundled
        # setuptools instead of relying on ambient network access.
        interpreter = shutil.which("python3.11") or sys.executable
        created = _run([interpreter, "-m", "venv", str(environment)], env=dict(os.environ))
        _record(results, "AC-01 disposable environment", created)
        if created.returncode:
            return _write_report(args.report, results)
        python = environment / "bin" / "python"
        graphori = environment / "bin" / "graphori"
        install = _run(
            [str(python), "-m", "pip", "install", "--no-build-isolation", "."],
            env=dict(os.environ), cwd=source,
        )
        _record(results, "AC-01 disposable clean installation", install)
        if install.returncode:
            return _write_report(args.report, results)

        root = tmp / "run-root"
        root.mkdir()
        fake_bin = tmp / "fake-bin"
        fake_bin.mkdir()
        fake_codex = fake_bin / "codex"
        fake_codex.write_text("#!/bin/sh\necho '--json --output-schema --ephemeral'\n", encoding="utf-8")
        fake_codex.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{fake_bin}:{environment / 'bin'}:/usr/bin:/bin"
        env.pop("ORCA_CLI_COMMAND", None)
        env.pop("ORCA_DEV_REPO_ROOT", None)

        help_result = _run([str(graphori), "--help"], env=env)
        help_result = _require(help_result, "작업 계획" in help_result.stdout, "Korean top-level help text missing")
        _record(results, "AC-02 help", help_result, "한국어 설명 포함=" + str("작업 계획" in help_result.stdout))
        doctor_before = sorted(root.rglob("*"))
        doctor = _run([str(graphori), "doctor", "--root", str(root), "--json"], env=env)
        doctor_after = sorted(root.rglob("*"))
        doctor_ok = (doctor_before == doctor_after and '"required": false' in doctor.stdout
                     and '"mode": "read_only"' in doctor.stdout)
        doctor = _require(doctor, doctor_ok, "doctor changed the disposable root or lost no-Orca/read-only contract")
        _record(results, "AC-02 doctor / AC-03 no Orca / AC-08 read-only", doctor,
                f"root_unchanged={doctor_before == doctor_after}; {doctor.stdout[-400:]}")
        plan = _run([str(graphori), "plan", "수용성 계획", "--root", str(root), "--json"], env=env)
        plan = _require(plan, "Graphori가 작업 계획을 만들었습니다." in plan.stdout,
                        "Korean default plan preview missing")
        _record(results, "AC-02 plan / AC-07 Korean CLI", plan,
                "한국어 계획 미리보기 포함=" + str("Graphori가 작업 계획을 만들었습니다." in plan.stdout))
        fake_run = _run([str(python), "-c", _fake_engine_script(), str(root)], env=env)
        _record(results, "AC-02 fake run / AC-03 no Orca", fake_run)

        legacy_root = tmp / "legacy-root"
        journal = legacy_root / ".graphori" / "runs" / "run-legacy-dashboard" / "journal" / "journal.jsonl"
        journal.parent.mkdir(parents=True)
        shutil.copyfile(legacy_fixture, journal)
        before = hashlib.sha256(journal.read_bytes()).hexdigest()
        replay = _run([str(graphori), "replay", "--root", str(legacy_root), "--run-id", "run-legacy-dashboard", "--json"], env=env)
        dashboard = _run([str(python), "-c", textwrap.dedent("""
            import json, sys
            from graphori_core.dashboard import DashboardStore
            value, events = DashboardStore(sys.argv[1]).snapshot("run-legacy-dashboard")
            assert value["terminal_status"] == "succeeded" and events
            print(json.dumps({"digest": value["projection_digest"], "events": len(events)}))
        """), str(legacy_root)], env=env)
        unchanged = before == hashlib.sha256(journal.read_bytes()).hexdigest()
        replay = _require(replay, unchanged and '"replay_verified": true' in replay.stdout,
                          "legacy journal was changed or replay marker missing")
        _record(results, "AC-04 legacy read-only replay / dashboard", replay,
                f"journal_sha256_unchanged={unchanged}; {replay.stdout[-300:]}")
        _record(results, "AC-02 dashboard projection", dashboard)

        ownership = _run(
            [str(python), "tests/test_journal_writer_ownership.py"], env=env, cwd=source,
        )
        _record(results, "AC-05 concurrent writer", ownership)
        resume = _run(
            [str(python), "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_pr11c_portability.py"],
            env=env, cwd=source,
        )
        _record(results, "AC-06 cold resume", resume)
    return _write_report(args.report, results)


def _write_report(path: Path, results: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    failed = [item["id"] for item in results if item["exit_code"] != 0]
    rows = "\n".join(
        f"| {item['id']} | {item['exit_code']} | `{item['evidence'].replace('|', '/').replace(chr(10), ' ')[:220]}` |"
        for item in results
    )
    verdict = "NOT_READY" if failed else "READY_WITH_LIMITATIONS"
    path.write_text(f"""# PR11D Production Release Acceptance

Generated by `scripts/release_acceptance.py`. This report is local execution
evidence, not an independent verification verdict.

## Result

**{verdict}**

Coordinator-held checks remain pending: actual Direct Codex/Claude E2E and
dashboard visual inspection. No paid provider or nested Graphori execution was
started by this harness. {"Failed local checks: " + ", ".join(failed) if failed else "No local harness command returned non-zero."}

| Acceptance evidence | Exit code | Detail |
| --- | ---: | --- |
{rows}

## Preservation boundary

All disposable run roots were created under the system temporary directory.
The legacy fixture was copied before replay and its SHA-256 was compared after
replay. The harness does not run `git clean`, reset, or journal mutation APIs
against the repository worktree.
""", encoding="utf-8")
    print(json.dumps({"report": str(path), "verdict": verdict, "failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
