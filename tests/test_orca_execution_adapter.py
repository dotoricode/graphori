import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.orca import (  # noqa: E402
    AdapterHealthState,
    OrcaLaunchStrategy,
    OrcaExecutionAdapter,
    OrcaJournalBridge,
    ReconciliationStatus,
    RuntimeResourceOwnership,
)
from graphori_adapters.orca.client import OrcaClient  # noqa: E402
from graphori_core import (  # noqa: E402
    AdapterError, ContextBundle, GraphExecutionEngine,
    NodeSpec,
    RouteCircuitBreaker, RouteHealthKey, RouteHealthStatus,
    RunConstraints,
    RunPlan,
    RunSpec,
)


FAKE_ORCA = r'''import json
import os
import pathlib
import sys

state_path = pathlib.Path(os.environ["FAKE_ORCA_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {
    "runs": [], "tasks": [], "log": [], "ack_attempts": 0, "release_attempts": 0,
    "dispatch_count": 0, "terminal_close_attempts": 0,
}
args = sys.argv[1:]
state["log"].append(args)
scenario = os.environ.get("FAKE_ORCA_SCENARIO", "success")

def save():
    state_path.write_text(json.dumps(state), encoding="utf-8")

def emit(result, ok=True):
    save()
    print(json.dumps({"id": "fixture", "ok": ok, "result": result,
                      "_meta": {"runtimeId": "runtime-fixture"}}))
    raise SystemExit(0 if ok else 1)

if args == ["--version"]:
    print("orca 1.4.fixture")
    save()
    raise SystemExit(0)
if args[:2] == ["skills", "get"]:
    print("# version matched " + args[2] + " guide")
    save()
    raise SystemExit(0)
if len(args) == 3 and args[0] == "orchestration" and args[2] == "--help":
    print("usage: orca orchestration " + args[1])
    save()
    raise SystemExit(0)
if len(args) == 3 and args[0] == "terminal" and args[2] == "--help":
    print("usage: orca terminal " + args[1])
    save()
    raise SystemExit(0)
if args[:2] == ["status", "--json"]:
    emit({"runtime": {"state": "ready", "runtimeId": "runtime-fixture",
                       "capabilities": ["orchestration.contract.v1"]}})
if args[:3] == ["orchestration", "run-list", "--json"]:
    emit({"runs": state["runs"]})
if args[:2] == ["orchestration", "run-create"]:
    objective = args[args.index("--objective") + 1]
    run = {
        "id": "orca-run-1", "objective": objective,
        "coordinator_handle": "term-coordinator",
    }
    state["runs"].append(run)
    emit({"run": run})
if args[:2] == ["orchestration", "task-list"]:
    emit({"tasks": state["tasks"]})
if args[:2] == ["orchestration", "task-create"]:
    spec = args[args.index("--spec") + 1]
    task = {"id": "orca-task-1", "spec": spec, "runId": "orca-run-1"}
    state["tasks"].append(task)
    emit({"task": task})
if args[:2] == ["terminal", "create"]:
    result = {"terminal": {"handle": "term-ready", "state": "running"}}
    if scenario == "placement_mismatch":
        result["launch"] = {"model": "wrong-model", "effort": "low"}
    emit(result)
if args[:2] == ["terminal", "wait"]:
    if scenario == "readiness_timeout":
        emit({"code": "terminal_wait_timeout"}, ok=False)
    emit({"terminal": {"handle": "term-ready"}, "condition": "tui-idle"})
if args[:2] == ["terminal", "close"]:
    state["terminal_close_attempts"] += 1
    if scenario == "terminal_close_failure":
        emit({"code": "terminal_close_failed"}, ok=False)
    emit({"terminal": {"handle": "term-ready"}, "state": "closed"})
if args[:2] == ["orchestration", "worker-start"]:
    if scenario == "worker_start_failure":
        emit({"code": "worker_start_failed"}, ok=False)
    state["dispatch_count"] += 1
    dispatch_id = "orca-dispatch-" + str(state["dispatch_count"])
    state["current_dispatch_id"] = dispatch_id
    emit({"dispatch": {"id": dispatch_id, "taskId": "orca-task-1",
                         "runId": "orca-run-1", "state": "ready"},
          "worker": {"agentTerminalHandle": "term-fixture"}})
if args[:2] == ["orchestration", "check"] and "--ack" not in args:
    if scenario == "capability_missing":
        emit({"code": "dispatch_capability_missing",
              "message": "Dispatch capability is missing",
              "runtimeOutputObserved": True}, ok=False)
    dispatch_id = state.get("current_dispatch_id", "orca-dispatch-1")
    messages = [{
        "id": "message-1", "type": "worker_done", "taskId": "orca-task-1",
        "dispatchId": dispatch_id, "outcome": "succeeded",
        "subject": "done", "body": "Completed bounded work.",
        "filesModified": ["src/a.py"],
    }]
    if scenario == "duplicate_delivery":
        messages.append(dict(messages[0]))
    if scenario == "malformed_delivery":
        messages[0]["filesModified"] = "src/a.py"
    emit({"delivery": {"id": "delivery-1", "messages": messages}})
if args[:2] == ["orchestration", "check"] and "--ack" in args:
    state["ack_attempts"] += 1
    journal = pathlib.Path(os.environ["FAKE_GRAPHORI_JOURNAL"])
    text = journal.read_text(encoding="utf-8") if journal.exists() else ""
    state["ack_after_journal"] = '"type":"worker_finished"' in text
    if scenario == "ack_fail_always":
        emit({"code": "temporary_ack_failure"}, ok=False)
    if scenario == "ack_fail_once" and state["ack_attempts"] == 1:
        emit({"code": "temporary_ack_failure"}, ok=False)
    emit({"count": 0, "acknowledged": args[args.index("--ack") + 1]})
if args[:2] == ["orchestration", "worker-release"]:
    state["release_attempts"] += 1
    if scenario == "release_failure":
        emit({"releaseState": "release_unknown", "error": "fixture"}, ok=False)
    emit({"releaseState": "released", "dispatchId": "orca-dispatch-1"})
if args[:2] == ["orchestration", "worker-show"]:
    emit({"dispatchId": "orca-dispatch-1", "taskId": "orca-task-1",
          "runId": "orca-run-1", "workerState": "running",
          "dispatchStatus": "dispatched"})
if args[:2] == ["orchestration", "worker-stop"]:
    emit({"state": "stopped", "dispatchId": "orca-dispatch-1"})
emit({"code": "unsupported", "args": args}, ok=False)
'''


class OrcaBridgeContractTests(unittest.TestCase):
    def test_delivery_identity_is_deterministic_and_worker_done_is_not_verdict(self):
        bridge = OrcaJournalBridge()
        delivery = {
            "id": "delivery-1",
            "messages": [{
                "id": "message-1", "type": "worker_done",
                "dispatchId": "dispatch-1", "taskId": "task-1",
                "outcome": "succeeded", "body": "done",
            }],
        }
        first = bridge.events(
            delivery, node_id="worker-a", expected_task_id="task-1",
            expected_dispatch_id="dispatch-1",
        )
        second = bridge.events(
            delivery, node_id="worker-a", expected_task_id="task-1",
            expected_dispatch_id="dispatch-1",
        )
        self.assertEqual(first, second)
        self.assertEqual(first[0].event_type, "worker_finished")
        self.assertEqual(first[0].payload["outcome"], "succeeded")
        self.assertNotIn("verdict", first[0].payload)

    def test_client_runs_commands_from_the_bound_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "cwd.py"
            script.write_text("import os; print(os.getcwd())", encoding="utf-8")
            client = OrcaClient((sys.executable, str(script)), cwd=root)
            response = client.call(())
            self.assertTrue(response.ok)
            self.assertEqual(Path(response.stdout.strip()).resolve(), root.resolve())


class OrcaExecutionAdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        self.script = self.workspace / "fake_orca.py"
        self.script.write_text(FAKE_ORCA, encoding="utf-8")
        self.state = self.workspace / "orca-state.json"
        self.run_id = "run-orca-adapter"
        self.journal = (
            self.workspace / ".graphori" / "runs" / self.run_id / "journal" / "journal.jsonl"
        )

    def adapter(self, scenario="success"):
        return OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": scenario,
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            delivery_timeout_ms=50,
        )

    def test_explicit_worktree_selector_is_forwarded_to_worker_start(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "success",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            worktree_selector="id:repo::/tmp/rrc-fixture",
        )
        plan = self.plan()

        async def dispatch_once():
            await adapter.prepare_run(plan)
            node = plan.nodes[0]
            session = await adapter.start_session(node)
            await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id="attempt:selector:1"),
            )

        asyncio.run(dispatch_once())
        log = json.loads(self.state.read_text())["log"]
        worker_start = next(
            args for args in log
            if args[:2] == ["orchestration", "worker-start"] and "--task" in args
        )
        self.assertEqual(
            worker_start[worker_start.index("--worktree") + 1],
            "id:repo::/tmp/rrc-fixture",
        )

    def test_blocked_exact_route_fails_probe_before_any_dispatch(self):
        seed = self.adapter()
        self.assertTrue(seed.probe().available)
        registry = RouteCircuitBreaker(self.workspace / "route-health.json")
        route_key = RouteHealthKey(
            str(seed.environment_evidence["orca_version"]),
            str(seed.environment_evidence["runtime_id"]),
            str(seed.environment_evidence["orca_guide_digest"]),
            "codex", "0.147.0",
        )
        registry.record(route_key, RouteHealthStatus.BLOCKED, "worker_done missing")
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "success",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            route_circuit_breaker=registry,
            route_health_key=route_key,
        )

        capabilities = adapter.probe()

        self.assertFalse(capabilities.available)
        self.assertIn("blocked", capabilities.reason.lower())
        log = json.loads(self.state.read_text())["log"]
        self.assertFalse(any(
            args[:2] == ["orchestration", "worker-start"] and "--task" in args
            for args in log
        ))

    def test_ready_terminal_waits_for_tui_idle_and_attaches_exact_handle(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "success",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
            ready_timeout_ms=250,
        )
        plan = self.plan(model="gpt-fixture", effort="high")

        async def dispatch_once():
            await adapter.prepare_run(plan)
            node = plan.nodes[0]
            session = await adapter.start_session(node)
            handle = await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id="attempt:ready:1"),
            )
            return handle

        handle = asyncio.run(dispatch_once())
        state = json.loads(self.state.read_text())
        log = state["log"]
        terminal_create_index = next(
            index for index, args in enumerate(log)
            if args[:2] == ["terminal", "create"] and "--command" in args
        )
        terminal_wait_index = next(
            index for index, args in enumerate(log)
            if args[:2] == ["terminal", "wait"] and "--for" in args
        )
        worker_start_index = next(
            index for index, args in enumerate(log)
            if args[:2] == ["orchestration", "worker-start"] and "--task" in args
        )
        self.assertLess(terminal_create_index, terminal_wait_index)
        self.assertLess(terminal_wait_index, worker_start_index)
        create = log[terminal_create_index]
        command = create[create.index("--command") + 1]
        self.assertIn("gpt-fixture", command)
        self.assertIn("model_reasoning_effort", command)
        worker_start = log[worker_start_index]
        self.assertEqual(worker_start[worker_start.index("--terminal") + 1], "term-ready")
        self.assertEqual(
            worker_start[worker_start.index("--from") + 1], "term-coordinator",
        )
        self.assertNotIn("--agent", worker_start)
        self.assertNotIn("--model", worker_start)
        self.assertNotIn("--effort", worker_start)
        self.assertEqual(adapter.resource_ownership[handle.value],
                         RuntimeResourceOwnership.GRAPHORI_PRECREATED)

    def test_ready_terminal_readiness_timeout_closes_terminal_without_dispatch(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "readiness_timeout",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
            ready_timeout_ms=25,
        )
        plan = self.plan(model="gpt-fixture", effort="high")

        async def dispatch_once():
            await adapter.prepare_run(plan)
            node = plan.nodes[0]
            session = await adapter.start_session(node)
            await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id="attempt:timeout:1"),
            )

        with self.assertRaises(AdapterError) as raised:
            asyncio.run(dispatch_once())
        self.assertEqual(raised.exception.error_kind, "OrcaAgentNotReady")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["terminal_close_attempts"], 1)
        self.assertFalse(any(
            args[:2] == ["orchestration", "worker-start"] and "--task" in args
            for args in state["log"]
        ))

    def test_ready_terminal_placement_mismatch_fails_closed_before_dispatch(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "placement_mismatch",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
        )
        plan = self.plan(model="gpt-fixture", effort="high")

        async def dispatch_once():
            await adapter.prepare_run(plan)
            node = plan.nodes[0]
            session = await adapter.start_session(node)
            await adapter.dispatch(
                session, node,
                ContextBundle(objective=node.objective, attempt_id="attempt:mismatch:1"),
            )

        with self.assertRaises(AdapterError) as raised:
            asyncio.run(dispatch_once())
        self.assertEqual(raised.exception.error_kind, "OrcaPlacementMismatch")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["terminal_close_attempts"], 1)
        self.assertFalse(any(
            args[:2] == ["orchestration", "worker-start"] and "--task" in args
            for args in state["log"]
        ))

    def test_ready_terminal_never_resends_after_dispatch_and_closes_owned_terminal(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "success",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            delivery_timeout_ms=50,
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
        )
        plan = self.plan(model="gpt-fixture", effort="high")
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def execute():
            handle = await engine.start(RunSpec(
                "ready terminal fixture", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            ))
            await engine.advance(handle.run_id)
            return engine.snapshot(handle.run_id)

        projection = asyncio.run(execute())
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["terminal_close_attempts"], 1)
        self.assertEqual(sum(
            args[:2] == ["orchestration", "worker-start"] and "--task" in args
            for args in state["log"]
        ), 1)
        self.assertFalse(any(args[:2] == ["terminal", "send"] for args in state["log"]))
        self.assertEqual(adapter.active_handles, 0)

    def test_ready_terminal_close_failure_degrades_release_health(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "terminal_close_failure",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            delivery_timeout_ms=50,
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
        )
        plan = self.plan(model="gpt-fixture", effort="high")
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def execute():
            handle = await engine.start(RunSpec(
                "ready terminal close failure", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            ))
            await engine.advance(handle.run_id)
            return engine.snapshot(handle.run_id)

        projection = asyncio.run(execute())
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        self.assertEqual(adapter.health.components["release"], AdapterHealthState.DEGRADED)
        self.assertEqual(
            adapter.resource_dispositions["orca-dispatch-1"], "release_failed",
        )
        state = json.loads(self.state.read_text())
        self.assertEqual(state["terminal_close_attempts"], 1)

    def test_ready_terminal_claude_command_preserves_model_and_effort(self):
        adapter = OrcaExecutionAdapter(
            workspace_root=self.workspace,
            executable=(sys.executable, str(self.script)),
            process_env={
                "FAKE_ORCA_STATE": str(self.state),
                "FAKE_ORCA_SCENARIO": "success",
                "FAKE_GRAPHORI_JOURNAL": str(self.journal),
            },
            launch_strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL,
        )
        base = self.plan(model="claude-fixture", effort="medium")
        node = base.nodes[0]
        plan = RunPlan(
            run_id=base.run_id, plan_version=1, status="committed",
            nodes=(NodeSpec.from_dict({**node.to_dict(), "provider": "claude"}),),
        )

        async def dispatch_once():
            await adapter.prepare_run(plan)
            current = plan.nodes[0]
            session = await adapter.start_session(current)
            await adapter.dispatch(
                session, current,
                ContextBundle(objective=current.objective, attempt_id="attempt:claude:1"),
            )

        asyncio.run(dispatch_once())
        log = json.loads(self.state.read_text())["log"]
        create = next(
            args for args in log
            if args[:2] == ["terminal", "create"] and "--command" in args
        )
        command = create[create.index("--command") + 1]
        self.assertIn("claude", command)
        self.assertIn("claude-fixture", command)
        self.assertIn("--effort medium", command)

    def plan(self, *, model="", effort=""):
        return RunPlan(
            run_id=self.run_id, plan_version=1, status="committed",
            nodes=(NodeSpec(
                "worker-a", "implementation", "Worker A", "Bounded work", "worker",
                provider="codex", worktree_policy="current",
                model=model, effort=effort,
                verification_policy="independent",
            ),),
        )

    def run_engine(self, scenario="success"):
        adapter = self.adapter(scenario)
        plan = self.plan()
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def execute():
            handle = await engine.start(RunSpec(
                "Orca adapter fixture", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            ))
            await engine.advance(handle.run_id)
            return engine.snapshot(handle.run_id), adapter

        return asyncio.run(execute())

    def test_full_delivery_is_journaled_before_ack_and_resource_is_released(self):
        projection, adapter = self.run_engine()
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        self.assertIsNone(projection.terminal_status)
        event_types = [event.event_type for event in projection.events]
        self.assertIn("runtime_binding_recorded", event_types)
        self.assertIn("worker_finished", event_types)
        self.assertIn("runtime_resource_changed", event_types)
        state = json.loads(self.state.read_text())
        self.assertTrue(state["ack_after_journal"])
        self.assertEqual(state["ack_attempts"], 1)
        self.assertEqual(state["release_attempts"], 1)
        self.assertEqual(adapter.health.components["delivery"], AdapterHealthState.HEALTHY)
        self.assertEqual(adapter.health.components["release"], AdapterHealthState.HEALTHY)
        self.assertEqual(adapter.active_handles, 0)

    def test_ack_retry_is_control_plane_only_and_idempotent(self):
        projection, adapter = self.run_engine("ack_fail_once")
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["ack_attempts"], 2)
        self.assertEqual(adapter.health.components["delivery"], AdapterHealthState.HEALTHY)

    def test_pending_ack_is_recovered_after_adapter_restart(self):
        projection, first = self.run_engine("ack_fail_always")
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        self.assertEqual(first.health.components["delivery"], AdapterHealthState.DEGRADED)

        recovered = self.adapter("success")
        asyncio.run(recovered.prepare_run(self.plan()))

        state = json.loads(self.state.read_text())
        self.assertEqual(state["ack_attempts"], 3)
        binding_path = (
            self.workspace / ".graphori" / "orca-bindings" / f"{self.run_id}.json"
        )
        binding = json.loads(binding_path.read_text())
        self.assertEqual(binding["pending_acks"], {})
        self.assertEqual(recovered.health.components["delivery"], AdapterHealthState.HEALTHY)

    def test_release_failure_does_not_rewrite_work_outcome(self):
        projection, adapter = self.run_engine("release_failure")
        self.assertEqual(projection.node_states["worker-a"], "awaiting_verification")
        self.assertEqual(adapter.health.components["release"], AdapterHealthState.DEGRADED)
        self.assertEqual(adapter.resource_dispositions["orca-dispatch-1"], "release_failed")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["release_attempts"], 2)

    def test_duplicate_delivery_is_one_transition_and_one_ack(self):
        projection, _adapter = self.run_engine("duplicate_delivery")
        worker_finished = [
            event for event in projection.events
            if event.event_type == "worker_finished" and event.node_id == "worker-a"
        ]
        self.assertEqual(len(worker_finished), 1)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["ack_attempts"], 1)

    def test_malformed_delivery_fails_closed_without_releasing_unsettled_worker(self):
        projection, adapter = self.run_engine("malformed_delivery")
        self.assertNotEqual(projection.node_states["worker-a"], "passed")
        self.assertEqual(adapter.health.components["delivery"], AdapterHealthState.DEGRADED)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["ack_attempts"], 0)
        self.assertEqual(state["release_attempts"], 0)
        self.assertEqual(adapter.active_handles, 1)

    def test_worker_done_capability_missing_fails_safe(self):
        projection, adapter = self.run_engine("capability_missing")
        self.assertNotEqual(projection.node_states["worker-a"], "passed")
        self.assertEqual(adapter.health.components["delivery"], AdapterHealthState.DEGRADED)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["release_attempts"], 0)
        self.assertEqual(adapter.active_handles, 1)

    def test_worker_start_failure_is_dispatch_degradation(self):
        projection, adapter = self.run_engine("worker_start_failure")
        self.assertNotEqual(projection.node_states["worker-a"], "passed")
        self.assertEqual(adapter.health.components["dispatch"], AdapterHealthState.DEGRADED)

    def test_run_and_task_bindings_are_exactly_once_across_adapter_restart(self):
        first = self.adapter()
        second = self.adapter()

        async def execute():
            await first.prepare_run(self.plan())
            await first.start_session(self.plan().nodes[0])
            await second.prepare_run(self.plan())
            await second.start_session(self.plan().nodes[0])

        asyncio.run(execute())
        state = json.loads(self.state.read_text())
        self.assertEqual(len(state["runs"]), 1)
        self.assertEqual(len(state["tasks"]), 1)

    def test_probe_records_version_runtime_guide_digest_and_truthful_reconcile(self):
        adapter = self.adapter()
        capabilities = adapter.probe()
        self.assertTrue(capabilities.available)
        self.assertFalse(capabilities.supports_reconcile)
        self.assertTrue(capabilities.supports_delivery_ack)
        evidence = adapter.environment_evidence
        self.assertEqual(evidence["resolved_executable"], sys.executable)
        self.assertEqual(evidence["orca_version"], "orca 1.4.fixture")
        self.assertEqual(evidence["runtime_id"], "runtime-fixture")
        self.assertTrue(evidence["orca_guide_digest"].startswith("sha256:"))
        self.assertTrue(all(evidence["command_support"].values()))
        self.assertTrue(all(evidence["terminal_command_support"].values()))

    def test_reconciliation_experiment_remains_non_mutating(self):
        adapter = self.adapter()
        status = adapter.classify_reconciliation(
            journal_state="running",
            observed={"workerState": "running", "dispatchStatus": "dispatched"},
        )
        self.assertEqual(status, ReconciliationStatus.STILL_RUNNING)
        self.assertFalse(adapter.probe().supports_reconcile)


@unittest.skipUnless(os.environ.get("GRAPHORI_LIVE_ORCA_TEST") == "1", "opt-in only")
class OrcaLiveSmokeTests(unittest.TestCase):
    def test_live_orca_smoke_is_explicit(self):
        self.skipTest("mutating live Orca smoke requires a temporary-repo harness")


if __name__ == "__main__":
    unittest.main()
