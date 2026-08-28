import asyncio
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter  # noqa: E402
from graphori_adapters.codex.adapter import CodexExecutionAdapter  # noqa: E402
from graphori_core import (  # noqa: E402
    ContextBundle, GraphExecutionEngine, NodeSpec, ProcessLimits,
    RunConstraints, RunPlan, RunSpec,
)


REPORT = {
    "schema_version": 1,
    "status": "succeeded",
    "summary": "Completed the bounded task.",
    "files_modified": [],
    "evidence": [{"kind": "test", "reference": "fixture"}],
    "limitations": [],
}


FAKE_CLI = r'''#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys
import time

provider = os.environ.get("FAKE_PROVIDER", "codex")
mode = os.environ.get("FAKE_MODE", "success")
args = sys.argv[1:]
if "--version" in args:
    print(f"{provider}-fixture 1.2.3")
    raise SystemExit(0)
if "--help" in args or (provider == "codex" and args == ["exec", "--help"]):
    if provider == "codex":
        print("exec --json --output-schema --ephemeral --sandbox --model")
    else:
        print("-p --output-format --json-schema --no-session-persistence --permission-mode "
              "--allowedTools --disallowedTools --disable-slash-commands --model")
    raise SystemExit(0)
if mode == "sleep":
    time.sleep(30)
if mode == "write":
    pathlib.Path(os.environ["FAKE_WRITE_PATH"]).write_text("provider change", encoding="utf-8")
if mode == "commit":
    target = pathlib.Path(os.environ["FAKE_WRITE_PATH"])
    target.write_text("provider committed change", encoding="utf-8")
    subprocess.run(["git", "add", target.name], check=True)
    subprocess.run(["git", "commit", "-qm", "provider commit"], check=True)
report = json.loads(os.environ["FAKE_REPORT"])
if mode == "missing":
    report = None
if provider == "codex":
    print(json.dumps({"type": "thread.started", "thread_id": "thr-fixture"}))
    if report is not None:
        print(json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps(report)}}))
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 2}}))
else:
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "ses-fixture",
                      "model": "claude-fixture"}))
    payload = {"type": "result", "subtype": "success", "is_error": False,
               "session_id": "ses-fixture", "usage": {"input_tokens": 2}}
    if report is not None:
        payload["structured_output"] = report
    print(json.dumps(payload))
if mode == "stderr":
    print("diagnostic warning", file=sys.stderr)
if mode == "nonzero":
    raise SystemExit(7)
'''


class ProviderAdapterCompatibilityMixin:
    adapter_class = None
    provider = ""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        subprocess.run(
            ["git", "-C", str(self.workspace), "config", "user.email", "fixture@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.workspace), "config", "user.name", "Fixture"], check=True,
        )
        (self.workspace / "tracked.txt").write_text("user baseline", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "baseline"], check=True)
        self.cli = self.workspace / "fake-cli.py"
        self.cli.write_text(FAKE_CLI, encoding="utf-8")
        self.cli.chmod(self.cli.stat().st_mode | stat.S_IXUSR)
        self.node = NodeSpec(
            "worker-a", "implementation", "Worker A", "Read project metadata", "worker",
            read_scope=(".",), write_scope=(), provider=self.provider,
        )

    def adapter(self, *, mode="success", report=None, limits=None, write_path=""):
        env = {
            "FAKE_PROVIDER": self.provider,
            "FAKE_MODE": mode,
            "FAKE_REPORT": json.dumps(report or REPORT),
        }
        if write_path:
            env["FAKE_WRITE_PATH"] = write_path
        return self.adapter_class(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.cli)),
            process_env=env,
            process_env_allowlist=frozenset({
                "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
                "FAKE_PROVIDER", "FAKE_MODE", "FAKE_REPORT", "FAKE_WRITE_PATH",
            }),
            limits=limits or ProcessLimits(timeout_seconds=5, grace_seconds=0.2),
        )

    def run_adapter(self, adapter, node=None):
        node = node or self.node

        async def scenario():
            session = await adapter.start_session(node)
            dispatch = await adapter.dispatch(
                session, node,
                ContextBundle(
                    objective=node.objective, attempt_id=f"attempt:{node.node_id}:1",
                    read_scope=node.read_scope, write_scope=node.write_scope,
                ),
            )
            events = [event async for event in adapter.events(dispatch)]
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result, events

        return asyncio.run(scenario())

    def test_structured_one_shot_result_is_not_a_verdict(self):
        adapter = self.adapter()
        capabilities = adapter.probe()
        self.assertTrue(capabilities.available)
        self.assertTrue(capabilities.supports_structured_result)
        self.assertFalse(capabilities.supports_reconcile)
        self.assertFalse(capabilities.supports_persistent_session)
        self.assertTrue(capabilities.supports_usage)
        result, events = self.run_adapter(adapter)
        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.summary, REPORT["summary"])
        self.assertEqual([event.event_type for event in events], ["worker_finished"])
        self.assertNotIn("verdict", events[0].payload)
        self.assertEqual(result.runtime_metadata["provider"], self.provider)
        self.assertIn("first_event_ms", result.runtime_metadata)
        self.assertIn("worker_report_ms", result.runtime_metadata)
        self.assertIn("provider_start_ms", result.runtime_metadata)
        self.assertIn("cleanup_ms", result.runtime_metadata)
        self.assertGreaterEqual(result.total_attempt_ms, result.execution_ms)
        self.assertEqual(adapter.active_handles, 0)

    def test_requested_effort_is_forwarded_to_the_provider_cli(self):
        adapter = self.adapter()
        node = NodeSpec(**{
            **self.node.__dict__, "model": "fixture-model", "effort": "medium",
        })
        command = adapter._command(
            adapter._envelope(node, ContextBundle(
                objective=node.objective, attempt_id="attempt:worker-a:1",
            )),
            self.workspace / "schema.json", node,
        )
        if self.provider == "codex":
            self.assertIn('model_reasoning_effort="medium"', command)
        else:
            self.assertIn("--effort", command)
            self.assertEqual(command[command.index("--effort") + 1], "medium")
            self.assertIn("--verbose", command)
            schema = json.loads(command[command.index("--json-schema") + 1])
            self.assertNotIn("$schema", schema)

    def test_engine_journal_keeps_worker_finished_awaiting_verification(self):
        adapter = self.adapter()
        node = NodeSpec(
            "worker-a", "implementation", "Worker A", "Read project metadata", "worker",
            read_scope=(".",), write_scope=(), provider=self.provider,
            verification_policy="independent",
        )
        plan = RunPlan(
            run_id=f"run-{self.provider}", plan_version=1, status="committed", nodes=(node,),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(RunSpec(
                "provider compatibility", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            ))
            await engine.advance(handle.run_id)
            return engine.snapshot(handle.run_id)

        projection = asyncio.run(scenario())
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        self.assertIsNone(projection.terminal_status)
        self.assertNotIn("verdict_recorded", [event.event_type for event in projection.events])
        digest = projection.projection_digest

        # A resumed engine is a new canonical writer.  The prior owner must
        # explicitly end its in-process session before restart/replay.
        engine.close(plan.run_id)
        replay = GraphExecutionEngine(adapter=self.adapter(), plan_factory=lambda _spec: plan)

        async def replay_scenario():
            handle = await replay.start(RunSpec(
                "provider compatibility", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            ))
            return replay.snapshot(handle.run_id)

        replayed = asyncio.run(replay_scenario())
        self.assertEqual(replayed.projection_digest, digest)
        replay.close(plan.run_id)

    def test_missing_report_and_nonzero_exit_are_distinct(self):
        missing, _ = self.run_adapter(self.adapter(mode="missing"))
        failed, _ = self.run_adapter(self.adapter(mode="nonzero"))
        self.assertEqual(missing.outcome, "incomplete_result")
        self.assertEqual(missing.exit_code, 0)
        self.assertEqual((failed.outcome, failed.exit_code), ("failed", 7))

    def test_stderr_is_diagnostic_not_protocol_input(self):
        result, _ = self.run_adapter(self.adapter(mode="stderr"))
        self.assertEqual(result.outcome, "succeeded")
        self.assertTrue(result.stderr_digest.startswith("sha256:"))

    def test_dirty_baseline_is_preserved_and_new_delta_is_observed(self):
        tracked = self.workspace / "tracked.txt"
        tracked.write_text("existing user edit", encoding="utf-8")
        result, _ = self.run_adapter(self.adapter())
        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.files_modified, ())
        self.assertEqual(tracked.read_text(encoding="utf-8"), "existing user edit")

        outside = self.workspace / "outside.txt"
        result, _ = self.run_adapter(self.adapter(mode="write", write_path=str(outside)))
        self.assertEqual(result.outcome, "scope_violation")
        self.assertEqual(result.files_modified, ("outside.txt",))

    def test_committed_change_cannot_hide_a_scope_violation(self):
        committed = self.workspace / "committed.txt"
        result, _ = self.run_adapter(
            self.adapter(mode="commit", write_path=str(committed)),
        )
        self.assertEqual(result.outcome, "scope_violation")
        self.assertIn("committed.txt", result.files_modified)

    def test_cancel_cleans_up_the_process(self):
        adapter = self.adapter(
            mode="sleep", limits=ProcessLimits(timeout_seconds=60, grace_seconds=0.1),
        )

        async def scenario():
            session = await adapter.start_session(self.node)
            dispatch = await adapter.dispatch(
                session, self.node,
                ContextBundle(objective="sleep", attempt_id="attempt:worker-a:1"),
            )
            await asyncio.sleep(0.1)
            await adapter.cancel(dispatch, "test")
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result

        result = asyncio.run(scenario())
        self.assertEqual(result.outcome, "cancelled")
        self.assertEqual(adapter.active_handles, 0)

    def test_timeout_is_distinct_and_cleans_up_the_process(self):
        result, _ = self.run_adapter(self.adapter(
            mode="sleep", limits=ProcessLimits(timeout_seconds=0.1, grace_seconds=0.1),
        ))
        self.assertEqual(result.outcome, "timed_out")
        self.assertTrue(result.timed_out)

    def test_old_cli_probe_fails_closed(self):
        self.cli.write_text(
            "#!/usr/bin/env python3\nimport sys\nprint('old cli')\n", encoding="utf-8",
        )
        adapter = self.adapter()
        capabilities = adapter.probe()
        self.assertFalse(capabilities.available)
        self.assertIn("required CLI capability", capabilities.reason)


class CodexExecutionAdapterTests(ProviderAdapterCompatibilityMixin, unittest.TestCase):
    adapter_class = CodexExecutionAdapter
    provider = "codex"


class ClaudeCodeExecutionAdapterTests(ProviderAdapterCompatibilityMixin, unittest.TestCase):
    adapter_class = ClaudeCodeExecutionAdapter
    provider = "claude"

    def test_noninteractive_worker_can_run_only_bounded_python_unittest_commands(self):
        adapter = self.adapter()
        node = NodeSpec(**{
            **self.node.__dict__,
            "write_scope": ("src/math_utils.py",),
            "model": "claude-fixture",
            "effort": "medium",
        })
        command = adapter._command(
            adapter._envelope(node, ContextBundle(
                objective=node.objective, attempt_id="attempt:worker-a:1",
                write_scope=node.write_scope,
            )),
            self.workspace / "schema.json", node,
        )

        self.assertIn("--allowedTools", command)
        allowed = command[command.index("--allowedTools") + 1]
        self.assertIn("Bash(python -m unittest *)", allowed)
        self.assertIn("Bash(python3 -m unittest *)", allowed)
        self.assertNotIn("Bash(*)", allowed)


class ProviderLiveSmokeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("GRAPHORI_LIVE_CODEX_TEST") == "1", "opt-in only")
    def test_codex_read_only_smoke(self):
        self._live_smoke(CodexExecutionAdapter)

    @unittest.skipUnless(os.environ.get("GRAPHORI_LIVE_CLAUDE_TEST") == "1", "opt-in only")
    def test_claude_read_only_smoke(self):
        self._live_smoke(ClaudeCodeExecutionAdapter)

    def _live_smoke(self, adapter_class):
        repo = Path(__file__).parents[1]
        adapter = adapter_class(workspace_root=repo)
        node = NodeSpec(
            "smoke", "research", "Smoke", "Read the project name from pyproject.toml", "worker",
            read_scope=("pyproject.toml",), write_scope=(),
        )

        async def scenario():
            session = await adapter.start_session(node)
            dispatch = await adapter.dispatch(
                session, node, ContextBundle(
                    objective=node.objective, attempt_id="attempt:smoke:1",
                    read_scope=node.read_scope,
                ),
            )
            result = await adapter.collect(dispatch)
            await adapter.release(session)
            return result

        result = asyncio.run(scenario())
        self.assertEqual(result.outcome, "succeeded")


if __name__ == "__main__":
    unittest.main()
