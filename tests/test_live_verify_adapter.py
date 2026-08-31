from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest

from graphori_adapters.direct import RoutedExecutionAdapter
from graphori_adapters.generic.adapter import GenericProcessAdapter, ProcessCommand
from graphori_adapters.live_verify import LiveVerifyAdapter, workspace_digest
from graphori_core.ports import ContextBundle
from graphori_core.process_supervisor import ProcessLimits
from graphori_core.run_plan import NodeSpec, RunPlan


PYTHON = sys.executable


class LiveVerifyAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def _exercise(self, root: Path, worker_script: str, *, live: bool,
                        mutate_command=None):
        worker = NodeSpec(
            "i1", "implementation", "Implement", "Implement", "worker",
            adapter="worker", provider="worker", write_scope=("result.txt",),
        )
        verifier = NodeSpec(
            "v1", "verification", "Verify", "Verify", "verifier",
            dependencies=("i1",), adapter="generic-process",
            provider="generic-process", read_scope=("result.txt",),
        )
        plan = RunPlan("run-live", 1, "committed", nodes=(worker, verifier))
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
        ) if live else routed)
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
        if mutate_command is not None:
            mutate_command(adapter, verify_command)
        verifier_session = await adapter.start_session(verifier)
        verifier_dispatch = await adapter.dispatch(
            verifier_session, verifier, ContextBundle.from_node(verifier),
        )
        events = [event async for event in adapter.events(verifier_dispatch)]
        result = await adapter.collect(verifier_dispatch)
        await adapter.release(verifier_session)
        if live:
            self.last_live_metrics = adapter.metrics()
        return time.perf_counter() - started, events, result

    async def test_exact_proof_overlaps_verification_with_worker_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (
                "from pathlib import Path; import time; "
                "Path('result.txt').write_text('ready'); time.sleep(0.9)"
            )
            duration, events, result = await self._exercise(root, script, live=True)
        self.assertLess(duration, 1.15)
        self.assertTrue(result.runtime_metadata["live_verify_reused"])
        self.assertEqual(events[-1].payload["verdict"], "pass")
        self.assertIn("subprocess:verifier-command:exit:0",
                      events[-1].payload["evidence_ids"])
        self.assertEqual(self.last_live_metrics["live_verify_eligible_count"], 1)
        self.assertEqual(self.last_live_metrics["live_verify_reuse_count"], 1)
        self.assertEqual(self.last_live_metrics["live_verify_fallback_count"], 0)

    async def test_changed_workspace_rejects_stale_proof_and_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (
                "from pathlib import Path; import time; "
                "Path('result.txt').write_text('ready'); time.sleep(0.3); "
                "Path('late.txt').write_text('changed'); time.sleep(0.2)"
            )
            _duration, _events, result = await self._exercise(root, script, live=True)
        self.assertNotIn("live_verify_reused", result.runtime_metadata)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.last_live_metrics["live_verify_fallback_count"], 1)
        self.assertEqual(
            self.last_live_metrics["live_verify_fallback_reasons"],
            {"source_changed": 1},
        )

    async def test_changed_action_key_falls_back_at_adoption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (
                "from pathlib import Path; import time; "
                "Path('result.txt').write_text('ready'); time.sleep(0.9)"
            )

            def mutate(adapter, command):
                adapter.commands["v1"] = replace(
                    command,
                    env={"GRAPHORI_VERIFY_MODE": "changed"},
                    env_allowlist=command.env_allowlist | {"GRAPHORI_VERIFY_MODE"},
                )

            _duration, _events, result = await self._exercise(
                root, script, live=True, mutate_command=mutate,
            )
        self.assertNotIn("live_verify_reused", result.runtime_metadata)
        self.assertEqual(
            self.last_live_metrics["live_verify_fallback_reasons"],
            {"adoption_action_key_changed": 1},
        )

    async def test_symlink_uncertainty_uses_the_normal_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("target")
            try:
                (root / "link.txt").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            script = (
                "from pathlib import Path; import time; "
                "Path('result.txt').write_text('ready'); time.sleep(0.9)"
            )
            _duration, events, result = await self._exercise(root, script, live=True)
        self.assertNotIn("live_verify_reused", result.runtime_metadata)
        self.assertEqual(events[-1].payload["verdict"], "pass")

    async def test_paired_fixture_clears_strict_speed_gate(self):
        baseline: list[float] = []
        live: list[float] = []
        script = (
            "from pathlib import Path; import time; "
            "Path('result.txt').write_text('ready'); time.sleep(0.9)"
        )
        for _ in range(3):
            with tempfile.TemporaryDirectory() as directory:
                duration, _events, _result = await self._exercise(
                    Path(directory), script, live=False,
                )
                baseline.append(duration)
            with tempfile.TemporaryDirectory() as directory:
                duration, _events, result = await self._exercise(
                    Path(directory), script, live=True,
                )
                live.append(duration)
                self.assertTrue(result.runtime_metadata["live_verify_reused"])
        improvement = 1 - (sum(live) / len(live)) / (sum(baseline) / len(baseline))
        self.assertGreaterEqual(improvement, 0.25)

    def test_workspace_digest_tracks_content_but_not_graphori_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_text("one")
            first = workspace_digest(root)
            (root / ".graphori").mkdir()
            (root / ".graphori" / "journal.jsonl").write_text("event")
            self.assertEqual(workspace_digest(root), first)
            (root / "source.txt").write_text("two")
            self.assertNotEqual(workspace_digest(root), first)


if __name__ == "__main__":
    unittest.main()
