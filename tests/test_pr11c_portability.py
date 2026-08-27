"""PR11C: no-Orca subprocess and read-only diagnostic contracts."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.direct import RoutedExecutionAdapter
from graphori_core import (
    AdapterCapabilities,
    DispatchHandle,
    ExecutionResult,
    GraphExecutionEngine,
    NodeSpec,
    RunPlan,
    RunSpec,
    RuntimeEvent,
    RuntimeRunHandle,
    SessionHandle,
)
from graphori_core import product_cli


ROOT = Path(__file__).parents[1]
PY = sys.executable


class _FakeDirect:
    adapter_id = "codex"

    def __init__(self):
        self.dispatched: list[str] = []

    def probe(self):
        return AdapterCapabilities("codex", True, max_concurrency=1)

    async def prepare_run(self, plan):
        return RuntimeRunHandle("codex", f"runtime:{plan.run_id}")

    async def start_session(self, node):
        return SessionHandle("codex", f"session:{node.node_id}")

    async def dispatch(self, session, node, context):
        self.dispatched.append(node.node_id)
        return DispatchHandle("codex", f"dispatch:{node.node_id}", node.node_id)

    async def events(self, dispatch):
        if dispatch.node_id == "n2":
            yield RuntimeEvent(
                "worker_finished", "n2", "verifier", {"outcome": "succeeded"},
            )
            yield RuntimeEvent(
                "verdict_recorded", "n2", "verifier",
                {
                    "verdict": "pass",
                    "target_node_ids": ["n1"],
                    "evidence_ids": ["fake:resume-verdict"],
                },
            )

    async def collect(self, dispatch):
        return ExecutionResult("succeeded", runtime_id=dispatch.value)

    async def acknowledge(self, event):
        return None

    async def cancel(self, dispatch, reason):
        return None

    async def release(self, session):
        return None


class _UnknownDirect(_FakeDirect):
    async def dispatch(self, session, node, context):
        self.dispatched.append(node.node_id)
        raise RuntimeError("uncertain post-dispatch failure")


def _isolated_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    # There is deliberately no Orca executable or skill root on PATH/PYTHONPATH.
    env["PATH"] = "/usr/bin:/bin"
    env.pop("ORCA_CLI_COMMAND", None)
    env.pop("ORCA_DEV_REPO_ROOT", None)
    return env


class Pr11CPortabilityTests(unittest.TestCase):
    def test_core_import_and_plan_work_without_orca(self):
        script = r'''
from pathlib import Path
from graphori_core.ports import AdapterCapabilities
import graphori_core
import graphori_core.product_cli as cli
class Fake:
    def probe(self): return AdapterCapabilities("fake", True)
cli._direct_adapters = lambda root, timeout: (Fake(), Fake())
assert cli.main(["plan", "작은 기능을 구현해줘", "--root", "/private/tmp", "--json"]) == 0
'''
        result = subprocess.run([PY, "-c", script], text=True, capture_output=True,
                                env=_isolated_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"plan"', result.stdout)

    def test_fake_direct_run_works_without_orca(self):
        with tempfile.TemporaryDirectory() as temp:
            script = r'''
import asyncio, sys
from graphori_adapters.direct import RoutedExecutionAdapter
from graphori_core import *
class Fake:
    adapter_id = "codex"
    def probe(self): return AdapterCapabilities("codex", True)
    async def prepare_run(self, plan): return RuntimeRunHandle("codex", "fake")
    async def start_session(self, node): return SessionHandle("codex", node.node_id)
    async def dispatch(self, session, node, context): return DispatchHandle("codex", node.node_id, node.node_id)
    async def events(self, dispatch):
        if False: yield None
    async def collect(self, dispatch): return ExecutionResult("succeeded", evidence_ids=("fake",))
    async def acknowledge(self, event): pass
    async def cancel(self, dispatch, reason): pass
    async def release(self, session): pass
plan = RunPlan("portable", 1, "committed", nodes=(NodeSpec("n", "research", "N", "read", "worker", adapter="codex", provider="codex", verification_policy="deterministic"),))
async def main():
    engine = GraphExecutionEngine(adapter=RoutedExecutionAdapter({"codex": Fake()}), plan_factory=lambda spec: plan)
    handle = await engine.start(RunSpec("read", "codex", sys.argv[1]))
    await engine.advance(handle.run_id)
    assert engine.snapshot(handle.run_id).terminal_status == "succeeded"
    from graphori_core.dashboard import DashboardStore
    from graphori_core.journal import RunPaths, replay_journal
    events, digest = replay_journal(RunPaths(sys.argv[1], "portable"))
    assert events and digest
    snapshot, replayed = DashboardStore(sys.argv[1]).snapshot("portable")
    assert snapshot["terminal_status"] == "succeeded" and replayed
asyncio.run(main())
'''
            result = subprocess.run([PY, "-c", script, temp], text=True, capture_output=True,
                                    env=_isolated_env())
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_doctor_is_read_only_and_explains_no_provider_in_the_chosen_language(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / ".graphori" / "skills.lock.json"
            marker.parent.mkdir(parents=True)
            marker.write_text('{"schema_version": 1}\n', encoding="utf-8")
            before = {path.relative_to(root): path.read_bytes()
                      for path in root.rglob("*") if path.is_file()}
            result = subprocess.run(
                [PY, "-m", "graphori_core.product_cli", "doctor", "--root", temp, "--json",
                 "--lang", "ko"],
                text=True, capture_output=True, env=_isolated_env(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value["mode"], "read_only")
            self.assertIn("사용 가능한 Direct provider가 없습니다", value["provider_summary"])
            self.assertFalse(value["orca"]["required"])
            after = {path.relative_to(root): path.read_bytes()
                     for path in root.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_resume_advances_every_safe_descendant_and_releases_writer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = RunPlan(
                "resume-chain", 1, "committed",
                nodes=(
                    NodeSpec("n1", "implementation", "one", "one", "worker",
                             adapter="codex", provider="codex",
                             verification_policy="deterministic"),
                    NodeSpec("n2", "verification", "two", "two", "verifier",
                             role="verifier", dependencies=("n1",),
                             adapter="codex", provider="codex",
                             verification_policy="deterministic"),
                ),
            )
            spec = RunSpec("resume", "codex", str(root.resolve()))
            first_adapter = _FakeDirect()
            first = GraphExecutionEngine(
                adapter=RoutedExecutionAdapter({"codex": first_adapter}),
                plan_factory=lambda _spec: plan,
            )

            async def prepare():
                handle = await first.start(spec)
                await first.advance(handle.run_id)
                first.close(handle.run_id)

            import asyncio
            asyncio.run(prepare())
            run_root = root / ".graphori" / "runs" / plan.run_id
            (run_root / "run-spec.json").write_text(
                json.dumps(spec.to_dict()), encoding="utf-8",
            )
            (run_root / "run-plan.json").write_text(
                json.dumps(plan.to_dict()), encoding="utf-8",
            )
            (run_root / "process-commands.json").write_text("{}", encoding="utf-8")
            resumed = _FakeDirect()
            unavailable = _FakeDirect()
            args = SimpleNamespace(root=root, run_id=plan.run_id, timeout=5,
                                   json=True, locale="ko")
            with patch.object(product_cli, "_direct_adapters",
                              return_value=(resumed, unavailable)):
                with redirect_stdout(StringIO()):
                    self.assertEqual(asyncio.run(product_cli._resume(args)), 0)
            self.assertEqual(resumed.dispatched, ["n2"])
            # A closed writer proves ownership was released before process exit.
            from graphori_core.journal import JournalWriter, RunPaths
            JournalWriter(RunPaths(root.resolve(), plan.run_id)).close()
            with self.assertRaisesRegex(ValueError, "terminal run"):
                product_cli._recorded_run(root, plan.run_id)

    def test_post_dispatch_unknown_is_not_automatically_redispatched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            plan = RunPlan(
                "resume-unknown", 1, "committed",
                nodes=(NodeSpec(
                    "n1", "implementation", "one", "one", "worker",
                    adapter="codex", provider="codex",
                    verification_policy="deterministic",
                ),),
            )
            spec = RunSpec("unknown", "codex", str(root))
            first = GraphExecutionEngine(
                adapter=RoutedExecutionAdapter({"codex": _UnknownDirect()}),
                plan_factory=lambda _spec: plan,
            )
            import asyncio

            async def prepare():
                handle = await first.start(spec)
                await first.advance(handle.run_id)
                first.close(handle.run_id)

            asyncio.run(prepare())
            run_root = root / ".graphori" / "runs" / plan.run_id
            (run_root / "run-spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
            (run_root / "run-plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            (run_root / "process-commands.json").write_text("{}", encoding="utf-8")
            resumed = _FakeDirect()
            args = SimpleNamespace(root=root, run_id=plan.run_id, timeout=5,
                                   json=True, locale="ko")
            with patch.object(product_cli, "_direct_adapters",
                              return_value=(resumed, _FakeDirect())):
                with redirect_stdout(StringIO()):
                    self.assertEqual(asyncio.run(product_cli._resume(args)), 1)
            self.assertEqual(resumed.dispatched, [])
            doctor_args = SimpleNamespace(root=root, run_id=None, timeout=1,
                                          json=True, locale="ko")
            output = StringIO()
            with patch.object(product_cli, "_direct_adapters",
                              return_value=(_FakeDirect(), _FakeDirect())):
                with redirect_stdout(output):
                    self.assertEqual(product_cli.cmd_doctor(doctor_args), 0)
            diagnosis = json.loads(output.getvalue())
            self.assertEqual(diagnosis["interrupted_runs"]["needs_review"], 1)
            self.assertEqual(
                diagnosis["interrupted_runs"]["runs"][0]["status"], "결과 확인 필요",
            )

    def test_core_and_product_skill_have_no_required_orca_dependency(self):
        offenders = []
        for path in (ROOT / "src" / "graphori_core").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "graphori_adapters.orca" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])
        skill = (ROOT / "skills" / "graphori" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("$orca-cli", skill)
        self.assertNotIn("skills get orchestration", skill)

    def test_provider_availability_combinations_do_not_consult_orca(self):
        class Probe:
            def __init__(self, available):
                self.available = available
                self.reason = None

        class Adapter:
            def __init__(self, available):
                self.available = available

            def probe(self):
                return Probe(self.available)

        from graphori_core.model_routing import Availability
        for codex, claude in ((True, True), (True, False), (False, True), (False, False)):
            values = product_cli._availability(Adapter(codex), Adapter(claude))
            self.assertEqual(values["gpt-5.6-luna"] is Availability.AVAILABLE, codex)
            self.assertEqual(values["claude-sonnet-5"] is Availability.AVAILABLE, claude)

    def test_codex_only_and_claude_only_can_plan_implementation(self):
        from graphori_core.model_routing import Availability
        from graphori_core.product import ProductPlanCompiler

        cases = (
            ({
                "gpt-5.6-luna": Availability.AVAILABLE,
                "gpt-5.6-terra": Availability.AVAILABLE,
                "gpt-5.6-sol": Availability.UNAVAILABLE,
                "claude-sonnet-5": Availability.UNAVAILABLE,
                "claude-opus-5": Availability.UNAVAILABLE,
            }, "codex"),
            ({
                "gpt-5.6-luna": Availability.UNAVAILABLE,
                "gpt-5.6-terra": Availability.UNAVAILABLE,
                "gpt-5.6-sol": Availability.UNAVAILABLE,
                "claude-sonnet-5": Availability.AVAILABLE,
                "claude-opus-5": Availability.UNAVAILABLE,
            }, "claude"),
        )
        for availability, expected in cases:
            plan = ProductPlanCompiler(availability=availability).compile(
                RunSpec("작은 기능을 구현해줘", "codex", "/workspace"),
                run_id=f"only-{expected}", write_scope=("result.txt",),
            ).plan
            implementation = next(node for node in plan.nodes if node.team_id == "implementation")
            self.assertEqual(implementation.provider, expected)

    def test_plan_without_any_direct_provider_has_clear_diagnostic(self):
        class Unavailable(_FakeDirect):
            def probe(self):
                return AdapterCapabilities("none", False, reason="missing")

        with tempfile.TemporaryDirectory() as temp:
            stderr = StringIO()
            with patch.object(product_cli, "_direct_adapters",
                              return_value=(Unavailable(), Unavailable())):
                with redirect_stderr(stderr):
                    result = product_cli.main(["plan", "작은 작업", "--root", temp])
            self.assertEqual(result, 2)
            self.assertIn("사용 가능한 Direct provider가 없습니다", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
