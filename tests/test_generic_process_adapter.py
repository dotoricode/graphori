import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.generic import GenericProcessAdapter, ProcessCommand  # noqa: E402
from graphori_core import (  # noqa: E402
    AdapterError, ContextBundle, EvidenceStore, GraphExecutionEngine, NodeSpec, ProcessLimits,
    RunConstraints, RunPlan, RunSpec, Scheduler, SchedulerPolicy, ensure_run_dirs,
)


PY = sys.executable


class GenericProcessAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.node = NodeSpec("worker-a", "implementation", "Worker A", "run command", "worker")

    def test_explicit_argv_process_returns_structured_success(self):
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={
                self.node.node_id: ProcessCommand(
                    argv=(PY, "-c", "import sys; sys.stdout.buffer.write(b'ok')"),
                ),
            },
        )

        async def scenario():
            session = await adapter.start_session(self.node)
            dispatch = await adapter.dispatch(
                session,
                self.node,
                ContextBundle(objective="run command", attempt_id="attempt:worker-a:1"),
            )
            events = [event async for event in adapter.events(dispatch)]
            self.assertEqual([event.event_type for event in events], ["worker_finished"])
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result

        result = asyncio.run(scenario())
        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.attempt_id, "attempt:worker-a:1")
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.cancelled)
        self.assertTrue(result.stdout_digest.startswith("sha256:"))
        self.assertEqual(adapter.active_handles, 0)

    def test_adapter_rejects_cwd_escape_without_running_process(self):
        error, active = self._dispatch_error(ProcessCommand(
            argv=(PY, "-c", "raise SystemExit('must not run')"), cwd="..",
        ))
        self.assertEqual(error.outcome, "startup_failure")
        self.assertEqual(error.error_kind, "PathSecurityError")
        self.assertEqual(active, 0)

    def test_capabilities_are_truthful(self):
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace, commands={}, max_concurrency=2,
        )
        capabilities = adapter.probe()
        self.assertEqual(capabilities.max_concurrency, 2)
        self.assertTrue(capabilities.supports_cancel)
        self.assertFalse(capabilities.supports_reconcile)
        self.assertFalse(capabilities.supports_heartbeat)
        self.assertFalse(capabilities.supports_progress)
        self.assertFalse(capabilities.supports_worktree)
        self.assertFalse(capabilities.supports_persistent_session)
        self.assertFalse(capabilities.supports_questions)
        self.assertFalse(capabilities.supports_gate)
        self.assertFalse(capabilities.supports_usage)
        self.assertFalse(capabilities.supports_files_modified)
        legacy = type(capabilities)("legacy", True, 3, True, True, "")
        self.assertEqual(legacy.max_concurrency, 3)

    def test_shell_command_string_is_rejected(self):
        with self.assertRaises(ValueError):
            ProcessCommand(argv=f"{PY} -c pass")

    def _run(self, command, *, node=None, evidence_store=None):
        node = node or self.node
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={node.node_id: command},
            evidence_store=evidence_store,
        )

        async def scenario():
            session = await adapter.start_session(node)
            dispatch = await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id=f"attempt:{node.node_id}:1"),
            )
            events = [event async for event in adapter.events(dispatch)]
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result, events, adapter.active_handles

        return asyncio.run(scenario())

    def _dispatch_error(self, command):
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={self.node.node_id: command},
        )

        async def scenario():
            session = await adapter.start_session(self.node)
            try:
                with self.assertRaises(AdapterError) as captured:
                    await adapter.dispatch(
                        session, self.node,
                        ContextBundle(objective="run", attempt_id="attempt:worker-a:1"),
                    )
                return captured.exception, adapter.active_handles
            finally:
                await adapter.release(session)

        return asyncio.run(scenario())

    def test_nonzero_timeout_and_spawn_failure_are_distinct(self):
        failed, _, active = self._run(ProcessCommand(argv=(PY, "-c", "raise SystemExit(7)")))
        self.assertEqual((failed.outcome, failed.exit_code, active), ("failed", 7, 0))

        timed_out, _, active = self._run(ProcessCommand(
            argv=(PY, "-c", "import time; time.sleep(30)"),
            limits=ProcessLimits(timeout_seconds=0.1, grace_seconds=0.2),
        ))
        self.assertEqual(timed_out.outcome, "timed_out")
        self.assertTrue(timed_out.timed_out)
        self.assertFalse(timed_out.cancelled)
        self.assertEqual(active, 0)

        startup, active = self._dispatch_error(
            ProcessCommand(argv=("missing-graphori-executable",)),
        )
        self.assertEqual(startup.outcome, "startup_failure")
        self.assertEqual(startup.error_kind, "FileNotFoundError")
        self.assertNotIn(str(self.workspace), startup.detail)
        self.assertEqual(active, 0)

    def test_bounded_binary_output_can_be_stored_as_optional_evidence(self):
        paths = ensure_run_dirs(self.workspace, "run-evidence")
        store = EvidenceStore(paths)
        result, _, _ = self._run(
            ProcessCommand(
                argv=(
                    PY, "-c",
                    "import sys; sys.stdout.buffer.write(b'\\xff' + b'A' * 1000); "
                    "sys.stderr.buffer.write(b'\\xfeERR')",
                ),
                limits=ProcessLimits(max_stdout_bytes=32, max_stderr_bytes=32),
                capture_evidence=True,
            ),
            evidence_store=store,
        )
        self.assertEqual(result.outcome, "succeeded")
        self.assertTrue(result.stdout_truncated)
        self.assertTrue(result.stdout_evidence_id)
        self.assertEqual(store.get(result.stdout_evidence_id), b"\xff" + b"A" * 31)
        self.assertEqual(store.get(result.stderr_evidence_id), b"\xfeERR")

    def test_environment_is_filtered_through_supervisor_policy(self):
        paths = ensure_run_dirs(self.workspace, "run-env")
        store = EvidenceStore(paths)
        result, _, _ = self._run(
            ProcessCommand(
                argv=(PY, "-c", (
                    "import os,sys; sys.stdout.write('|'.join("
                    "[os.getenv('GRAPHORI_SAFE',''), os.getenv('GRAPHORI_SECRET_TOKEN','missing')]))"
                )),
                env={"GRAPHORI_SAFE": "visible", "GRAPHORI_SECRET_TOKEN": "hidden"},
                env_allowlist=frozenset({"PATH", "HOME", "GRAPHORI_SAFE", "GRAPHORI_SECRET_TOKEN"}),
                capture_evidence=True,
            ),
            evidence_store=store,
        )
        self.assertEqual(store.get(result.stdout_evidence_id), b"visible|missing")

    def test_cancel_stops_process_and_cleans_handle(self):
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={
                self.node.node_id: ProcessCommand(
                    argv=(PY, "-c", "import time; time.sleep(30)"),
                    limits=ProcessLimits(grace_seconds=0.2),
                ),
            },
        )

        async def scenario():
            session = await adapter.start_session(self.node)
            dispatch = await adapter.dispatch(
                session, self.node,
                ContextBundle(objective="wait", attempt_id="attempt:worker-a:1"),
            )
            await adapter.cancel(dispatch, "test")
            await asyncio.wait_for(
                asyncio.create_task(_drain(adapter.events(dispatch))), timeout=2,
            )
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result

        result = asyncio.run(scenario())
        self.assertEqual(result.outcome, "cancelled")
        self.assertTrue(result.cancelled)
        self.assertFalse(result.timed_out)
        self.assertEqual(adapter.active_handles, 0)

    def test_adapter_limit_rejects_hidden_queueing(self):
        nodes = tuple(
            NodeSpec(name, "research", name.upper(), name, "worker")
            for name in ("a", "b", "c")
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={node.node_id: ProcessCommand(
                argv=(PY, "-c", "import time; time.sleep(30)"),
                limits=ProcessLimits(grace_seconds=0.2),
            ) for node in nodes},
            max_concurrency=2,
        )

        async def scenario():
            sessions = [await adapter.start_session(node) for node in nodes]
            dispatches = []
            for index in range(2):
                dispatches.append(await adapter.dispatch(
                    sessions[index], nodes[index],
                    ContextBundle(objective=nodes[index].objective,
                                  attempt_id=f"attempt:{nodes[index].node_id}:1"),
                ))
            with self.assertRaisesRegex(RuntimeError, "scheduler must apply backpressure"):
                await adapter.dispatch(
                    sessions[2], nodes[2],
                    ContextBundle(objective="c", attempt_id="attempt:c:1"),
                )
            for dispatch in dispatches:
                await adapter.cancel(dispatch, "cleanup")
            for dispatch in dispatches:
                await _drain(adapter.events(dispatch))
                await adapter.collect(dispatch)
            for session in sessions:
                await adapter.release(session)

        asyncio.run(scenario())
        self.assertEqual(adapter.active_handles, 0)

    def test_cancel_terminates_descendant_tree(self):
        child = self.workspace / "child.py"
        parent = self.workspace / "parent.py"
        child.write_text(
            "import pathlib,time\n"
            "pathlib.Path('child-started').write_text('1')\n"
            "time.sleep(0.8)\n"
            "pathlib.Path('child-survived').write_text('1')\n",
            encoding="utf-8",
        )
        parent.write_text(
            "import subprocess,sys,time\n"
            "subprocess.Popen([sys.executable, 'child.py'])\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={self.node.node_id: ProcessCommand(
                argv=(PY, "parent.py"), limits=ProcessLimits(grace_seconds=0.2),
            )},
        )

        async def scenario():
            session = await adapter.start_session(self.node)
            dispatch = await adapter.dispatch(
                session, self.node,
                ContextBundle(objective="tree", attempt_id="attempt:worker-a:1"),
            )
            for _ in range(100):
                if (self.workspace / "child-started").exists():
                    break
                await asyncio.sleep(0.01)
            self.assertTrue((self.workspace / "child-started").exists())
            await adapter.cancel(dispatch, "tree cleanup")
            await _drain(adapter.events(dispatch))
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            await asyncio.sleep(1.0)
            return result

        result = asyncio.run(scenario())
        self.assertEqual(result.outcome, "cancelled")
        self.assertFalse((self.workspace / "child-survived").exists())


class GenericProcessEngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)

    def test_real_workers_fan_in_and_explicit_verdict_replay(self):
        worker_script = (
            "import pathlib,sys,time; time.sleep(0.2); "
            "pathlib.Path(sys.argv[1]).write_text(sys.argv[1])"
        )
        verifier_script = (
            "import json,pathlib; "
            "assert pathlib.Path('a.txt').read_text() == 'a.txt'; "
            "assert pathlib.Path('b.txt').read_text() == 'b.txt'; "
            "pathlib.Path('verdict.json').write_text(json.dumps("
            "{'verdict':'pass','evidence_ids':['ev:generic-verifier']}))"
        )
        commands = {
            "a": ProcessCommand(argv=(PY, "-c", worker_script, "a.txt")),
            "b": ProcessCommand(argv=(PY, "-c", worker_script, "b.txt")),
            "verify": ProcessCommand(
                argv=(PY, "-c", verifier_script), verdict_file="verdict.json",
            ),
        }
        plan = RunPlan(
            run_id="run-generic-e2e", plan_version=1, status="committed",
            nodes=(
                NodeSpec(
                    "a", "research", "A", "write A", "worker",
                    read_scope=("a",), verification_policy="independent",
                    estimated_execution_ms=90_000,
                ),
                NodeSpec(
                    "b", "research", "B", "write B", "worker",
                    read_scope=("b",), verification_policy="independent",
                    estimated_execution_ms=80_000,
                ),
                NodeSpec(
                    "verify", "verification", "Verify", "verify outputs", "verifier",
                    dependencies=("a", "b"), verification_policy="independent",
                    estimated_execution_ms=30_000,
                ),
            ),
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace, commands=commands, max_concurrency=2,
        )
        engine = GraphExecutionEngine(
            adapter=adapter, plan_factory=lambda _spec: plan,
            scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
        )
        run_spec = RunSpec(
            "generic e2e", "test", str(self.workspace),
            constraints=RunConstraints(max_parallelism=2),
        )

        async def scenario():
            handle = await engine.start(run_spec)
            first = await engine.advance(handle.run_id)
            self.assertEqual(
                tuple(item.node_id for item in first.scheduling.dispatches), ("a", "b"),
            )
            self.assertEqual(
                engine.snapshot(handle.run_id).node_states,
                {"a": "awaiting_verification", "b": "awaiting_verification", "verify": "pending"},
            )
            second = await engine.advance(handle.run_id)
            self.assertEqual(
                tuple(item.node_id for item in second.scheduling.dispatches), ("verify",),
            )
            before = engine.snapshot(handle.run_id)
            self.assertEqual(before.terminal_status, "succeeded")

            restarted = GraphExecutionEngine(
                adapter=GenericProcessAdapter(
                    workspace_root=self.workspace, commands=commands, max_concurrency=2,
                ),
                plan_factory=lambda _spec: plan,
            )
            await restarted.start(run_spec)
            after = restarted.snapshot(handle.run_id)
            self.assertEqual(after.projection_digest, before.projection_digest)
            self.assertEqual(after.node_states, before.node_states)

        asyncio.run(scenario())
        self.assertEqual(adapter.active_handles, 0)
        journal = (
            self.workspace / ".graphori" / "runs" / plan.run_id
            / "journal" / "journal.jsonl"
        )
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        worker_finishes = [event for event in events if event["type"] == "worker_finished"]
        self.assertEqual(len(worker_finishes), 3)
        self.assertTrue(all("stdout_digest" in event["payload"] for event in worker_finishes))
        verdicts = [event for event in events if event["type"] == "verdict_recorded"]
        self.assertEqual(len(verdicts), 1)

    def test_verifier_exit_zero_without_verdict_does_not_pass(self):
        plan = RunPlan(
            run_id="run-no-implicit-verdict", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "verify", "verification", "Verify", "verify", "verifier",
                verification_policy="independent",
            ),),
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={"verify": ProcessCommand(argv=(PY, "-c", "pass"))},
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
        run_spec = RunSpec("verifier", "test", str(self.workspace))

        async def scenario():
            handle = await engine.start(run_spec)
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.node_states["verify"], "awaiting_verification")
            self.assertIsNone(snapshot.terminal_status)

        asyncio.run(scenario())

    def test_explicit_exit_verdict_passes_without_wrapper_or_verdict_file(self):
        plan = RunPlan(
            run_id="run-direct-verdict", plan_version=1, status="committed",
            nodes=(
                NodeSpec(
                    "worker", "implementation", "Worker", "work", "worker",
                    verification_policy="independent",
                ),
                NodeSpec(
                    "verify", "verification", "Verify", "verify", "verifier",
                    dependencies=("worker",), verification_policy="independent",
                    acceptance_criteria=("AC-01: command passes",),
                ),
            ),
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={
                "worker": ProcessCommand(argv=(PY, "-c", "pass")),
                "verify": ProcessCommand(
                    argv=(PY, "-c", "pass"), verdict_from_exit=True,
                    criterion_ids=("AC-01",),
                ),
            },
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(RunSpec("verify", "test", str(self.workspace)))
            await engine.advance(handle.run_id)
            await engine.advance(handle.run_id)
            return engine.snapshot(handle.run_id)

        snapshot = asyncio.run(scenario())
        self.assertEqual(snapshot.node_states["worker"], "passed")
        self.assertEqual(snapshot.node_states["verify"], "passed")
        self.assertEqual(snapshot.terminal_status, "succeeded")

    def test_verifier_cannot_reuse_stale_verdict_file(self):
        (self.workspace / "verdict.json").write_text(
            json.dumps({"verdict": "pass", "evidence_ids": ["ev:stale"]}),
            encoding="utf-8",
        )
        verifier = NodeSpec(
            "verify", "verification", "Verify", "verify", "verifier",
            verification_policy="independent",
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={"verify": ProcessCommand(
                argv=(PY, "-c", "pass"), verdict_file="verdict.json",
            )},
        )

        async def scenario():
            session = await adapter.start_session(verifier)
            dispatch = await adapter.dispatch(
                session, verifier,
                ContextBundle(objective="verify", attempt_id="attempt:verify:1"),
            )
            events = [event async for event in adapter.events(dispatch)]
            await adapter.collect(dispatch)
            await adapter.release(session)
            return events

        events = asyncio.run(scenario())
        self.assertEqual([event.event_type for event in events], ["worker_finished"])

    def test_engine_cancel_terminates_real_process_and_journals_cancelled(self):
        plan = RunPlan(
            run_id="run-cancel-process", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "worker", "implementation", "Worker", "wait", "worker",
                verification_policy="independent",
            ),),
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={"worker": ProcessCommand(
                argv=(PY, "-c", "import time; time.sleep(30)"),
                limits=ProcessLimits(grace_seconds=0.2),
            )},
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
        run_spec = RunSpec("cancel", "test", str(self.workspace))

        async def scenario():
            handle = await engine.start(run_spec)
            advancing = asyncio.create_task(engine.advance(handle.run_id))
            for _ in range(100):
                if engine.snapshot(handle.run_id).node_states["worker"] == "running":
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(adapter.active_handles, 1)
            await engine.cancel(handle.run_id, "test cancellation")
            await asyncio.wait_for(advancing, timeout=3)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.node_states["worker"], "cancelled")
            self.assertEqual(snapshot.terminal_status, "cancelled")
            self.assertEqual(adapter.active_handles, 0)

        asyncio.run(scenario())

    def test_spawn_failure_retries_once_without_claiming_running(self):
        plan = RunPlan(
            run_id="run-spawn-failure", plan_version=1, status="committed",
            nodes=(NodeSpec("worker", "implementation", "Worker", "run", "worker"),),
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={"worker": ProcessCommand(argv=("missing-graphori-executable",))},
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
        run_spec = RunSpec("spawn failure", "test", str(self.workspace))

        async def scenario():
            handle = await engine.start(run_spec)
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.retry_counts["worker"], 1)
            self.assertEqual(snapshot.node_states["worker"], "blocked")
            self.assertEqual(snapshot.terminal_status, "blocked")
            return snapshot.events

        events = asyncio.run(scenario())
        startup = [
            event for event in events
            if event.event_type == "worker_finished"
            and event.payload.get("outcome") == "startup_failure"
        ]
        self.assertEqual(len(startup), 2)
        self.assertFalse(any(
            event.event_type == "node_status_changed"
            and event.payload.get("status") == "running"
            for event in events
        ))
        self.assertEqual(adapter.active_handles, 0)

    def test_two_process_intervals_really_overlap(self):
        nodes = (
            NodeSpec("a", "research", "A", "A", "worker"),
            NodeSpec("b", "research", "B", "B", "worker"),
        )
        script = (
            "import json,pathlib,sys,time; "
            "start=time.monotonic(); time.sleep(0.35); end=time.monotonic(); "
            "pathlib.Path(sys.argv[1]).write_text(json.dumps([start,end]))"
        )
        adapter = GenericProcessAdapter(
            workspace_root=self.workspace,
            commands={node.node_id: ProcessCommand(
                argv=(PY, "-c", script, f"{node.node_id}.json"),
            ) for node in nodes},
            max_concurrency=2,
        )

        async def execute(node):
            session = await adapter.start_session(node)
            dispatch = await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id=f"attempt:{node.node_id}:1"),
            )
            await _drain(adapter.events(dispatch))
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result

        results = asyncio.run(_gather(*(execute(node) for node in nodes)))
        self.assertTrue(all(result.outcome == "succeeded" for result in results))
        a_start, a_end = json.loads((self.workspace / "a.json").read_text())
        b_start, b_end = json.loads((self.workspace / "b.json").read_text())
        self.assertLess(max(a_start, b_start), min(a_end, b_end))
        self.assertEqual(adapter.active_handles, 0)


async def _drain(iterator):
    return [item async for item in iterator]


async def _gather(*awaitables):
    return await asyncio.gather(*awaitables)


if __name__ == "__main__":
    unittest.main()
