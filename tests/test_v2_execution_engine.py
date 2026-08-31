import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    AdapterCapabilities, ContextBundle, DispatchHandle, ExecutionResult,
    GraphExecutionEngine, NodeSpec, RunConstraints, RunPlan, RunSpec,
    RuntimeEvent, RuntimeRunHandle, Scheduler, SchedulerPolicy, SessionHandle,
    StateTransitionError, ActivationScope, SkillBinding,
)
from graphori_core.workspace_snapshot import workspace_digest  # noqa: E402


class ConcurrentFakeAdapter:
    adapter_id = "fake"

    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.started = []
        self.closed_runs = []

    def probe(self):
        return AdapterCapabilities(adapter_id=self.adapter_id, available=True,
                                   max_concurrency=8)

    async def prepare_run(self, plan):
        return RuntimeRunHandle(self.adapter_id, plan.run_id)

    async def start_session(self, node):
        return SessionHandle(self.adapter_id, f"session:{node.node_id}")

    async def dispatch(self, session, node, context):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.append(node.node_id)
        return DispatchHandle(self.adapter_id, f"dispatch:{node.node_id}", node.node_id)

    async def events(self, dispatch):
        await asyncio.sleep(0.02)
        actor = "verifier" if dispatch.node_id == "verify" else "worker"
        yield RuntimeEvent("worker_finished", dispatch.node_id, actor,
                           {"outcome": "succeeded"})
        if dispatch.node_id == "verify":
            yield RuntimeEvent("verdict_recorded", dispatch.node_id, "verifier",
                               {"verdict": "pass", "evidence_ids": ["ev-verify"]})

    async def cancel(self, dispatch, reason):
        return None

    async def collect(self, dispatch):
        self.active -= 1
        return ExecutionResult("succeeded", evidence_ids=(f"ev:{dispatch.node_id}",))

    async def release(self, session):
        return None

    async def close_run(self, run_id):
        self.closed_runs.append(run_id)


class RetryOnceAdapter(ConcurrentFakeAdapter):
    def __init__(self):
        super().__init__()
        self.collections = 0

    async def events(self, dispatch):
        if self.collections:
            yield RuntimeEvent("worker_finished", dispatch.node_id, "worker",
                               {"outcome": "succeeded"})

    async def collect(self, dispatch):
        self.active -= 1
        self.collections += 1
        if self.collections == 1:
            return ExecutionResult("timed_out")
        return ExecutionResult("succeeded", evidence_ids=("ev-retry",))


class ReviseOnceAdapter(ConcurrentFakeAdapter):
    def __init__(self, workspace="."):
        super().__init__()
        self.contexts = {}
        self.workspace = Path(workspace)

    async def dispatch(self, session, node, context):
        self.contexts[node.node_id] = context
        return await super().dispatch(session, node, context)

    async def events(self, dispatch):
        await asyncio.sleep(0)
        is_verifier = dispatch.node_id.startswith("verify")
        payload = {"outcome": "succeeded"}
        if dispatch.node_id == "work":
            payload["runtime_metadata"] = {"provider_session": {
                "provider": "codex", "opaque_id": "a" * 32,
                "boundary_digest": "sha256:boundary",
                "attempt_id": "attempt:work:1", "observed_model": "model",
                "resumable": True,
            }}
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id,
            "verifier" if is_verifier else "worker",
            payload,
        )
        if is_verifier:
            verdict = "revise" if dispatch.node_id == "verify" else "pass"
            evidence = {"verdict": verdict, "evidence_ids": [f"ev:{dispatch.node_id}"]}
            if verdict == "revise":
                evidence.update({
                    "verification_command": ["python", "-m", "unittest"],
                    "verification_exit_code": 1,
                    "workspace_digest": workspace_digest(Path(self.workspace)),
                    "criterion_evidence": {
                        "AC-01": {"status": "FAILED", "evidence_ids": ["ev:verify"]},
                    },
                })
            yield RuntimeEvent(
                "verdict_recorded", dispatch.node_id, "verifier",
                evidence,
            )


class AlwaysTimeoutAdapter(RetryOnceAdapter):
    async def events(self, dispatch):
        if False:
            yield

    async def collect(self, dispatch):
        self.active -= 1
        self.collections += 1
        return ExecutionResult("timed_out")


class OutcomeUnknownAdapter(ConcurrentFakeAdapter):
    async def events(self, dispatch):
        if False:
            yield

    async def collect(self, dispatch):
        self.active -= 1
        return ExecutionResult("outcome_unknown")


class AlwaysReviseAdapter(ReviseOnceAdapter):
    async def events(self, dispatch):
        await asyncio.sleep(0)
        is_verifier = dispatch.node_id.startswith("verify")
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id,
            "verifier" if is_verifier else "worker",
            {"outcome": "succeeded"},
        )
        if is_verifier:
            yield RuntimeEvent(
                "verdict_recorded", dispatch.node_id, "verifier",
                {"verdict": "revise", "evidence_ids": [f"ev:{dispatch.node_id}"]},
            )


class NoCancelAdapter(ConcurrentFakeAdapter):
    def __init__(self):
        super().__init__()
        self.cancel_called = False
        self.running = asyncio.Event()
        self.finish = asyncio.Event()

    def probe(self):
        return AdapterCapabilities(
            adapter_id=self.adapter_id, available=True, max_concurrency=1,
            supports_cancel=False,
        )

    async def events(self, dispatch):
        self.running.set()
        await self.finish.wait()
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id, "worker", {"outcome": "succeeded"},
        )

    async def cancel(self, dispatch, reason):
        self.cancel_called = True


def spec(workspace="/workspace"):
    return RunSpec("parallel fixture", "test", str(workspace),
                   constraints=RunConstraints(max_parallelism=2))


class V2ExecutionEngineContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)

    def test_default_scheduler_respects_run_parallelism_limit(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-limited", plan_version=1, status="committed",
            nodes=(
                NodeSpec("a", "research", "A", "read A", "worker",
                         read_scope=("a",), estimated_execution_ms=90_000),
                NodeSpec("b", "research", "B", "read B", "worker",
                         read_scope=("b",), estimated_execution_ms=80_000),
            ),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            limited = RunSpec(
                "limited fixture", "test", str(self.workspace),
                constraints=RunConstraints(max_parallelism=1),
            )
            handle = await engine.start(limited)
            first = await engine.advance(handle.run_id)
            self.assertEqual(len(first.scheduling.dispatches), 1)
            self.assertEqual(engine.snapshot(handle.run_id).terminal_status, None)
            await engine.advance(handle.run_id)
            self.assertEqual(engine.snapshot(handle.run_id).terminal_status, "succeeded")

        asyncio.run(scenario())
        self.assertEqual(adapter.max_active, 1)

    def test_default_scheduler_respects_adapter_parallelism_limit(self):
        adapter = ConcurrentFakeAdapter()
        adapter.probe = lambda: AdapterCapabilities(
            adapter_id=adapter.adapter_id, available=True, max_concurrency=1,
        )
        plan = RunPlan(
            run_id="run-adapter-limited", plan_version=1, status="committed",
            nodes=(
                NodeSpec("a", "research", "A", "read A", "worker",
                         read_scope=("a",), estimated_execution_ms=90_000),
                NodeSpec("b", "research", "B", "read B", "worker",
                         read_scope=("b",), estimated_execution_ms=80_000),
            ),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            first = await engine.advance(handle.run_id)
            self.assertEqual(len(first.scheduling.dispatches), 1)
            await engine.advance(handle.run_id)

        asyncio.run(scenario())
        self.assertEqual(adapter.max_active, 1)

    def test_engine_does_not_call_unsupported_cancel_capability(self):
        adapter = NoCancelAdapter()
        plan = RunPlan(
            run_id="run-no-cancel", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "research", "A", "read", "worker"),),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            advancing = asyncio.create_task(engine.advance(handle.run_id))
            await adapter.running.wait()
            with self.assertRaisesRegex(RuntimeError, "does not support cancellation"):
                await engine.cancel(handle.run_id, "unsupported")
            self.assertFalse(adapter.cancel_called)
            adapter.finish.set()
            await advancing

        asyncio.run(scenario())

    def test_cancelled_run_closes_private_provider_state(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-cancel-cleanup", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "research", "A", "read", "worker"),),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            await engine.cancel(handle.run_id, "user request")
            self.assertEqual(engine.snapshot(handle.run_id).terminal_status, "cancelled")

        asyncio.run(scenario())
        self.assertEqual(adapter.closed_runs, [plan.run_id])

    def test_two_workers_run_in_parallel_then_fan_in_verifier_runs(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-engine", plan_version=1, status="committed",
            nodes=(
                NodeSpec("a", "research", "A", "read A", "worker",
                         read_scope=("a",), verification_policy="independent",
                         estimated_execution_ms=90_000),
                NodeSpec("b", "research", "B", "read B", "worker",
                         read_scope=("b",), verification_policy="independent",
                         estimated_execution_ms=80_000),
                NodeSpec("verify", "verification", "Verify", "verify A and B", "verifier",
                         dependencies=("a", "b"), verification_policy="independent",
                         estimated_execution_ms=30_000),
            ),
            critical_path=("a", "verify"),
        )
        engine = GraphExecutionEngine(
            adapter=adapter,
            plan_factory=lambda _spec: plan,
            scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
        )

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            first = await engine.advance(handle.run_id)
            self.assertEqual(tuple(item.node_id for item in first.scheduling.dispatches),
                             ("a", "b"))
            self.assertEqual(engine.snapshot(handle.run_id).node_states,
                             {"a": "awaiting_verification",
                              "b": "awaiting_verification", "verify": "pending"})
            second = await engine.advance(handle.run_id)
            self.assertEqual(tuple(item.node_id for item in second.scheduling.dispatches),
                             ("verify",))
            self.assertEqual(engine.snapshot(handle.run_id).terminal_status, "succeeded")

        asyncio.run(scenario())
        self.assertEqual(adapter.max_active, 2)
        self.assertEqual(adapter.started, ["a", "b", "verify"])

    def test_sprout_proofs_gate_pilot_fanout_fanin_and_commit(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-sprout-e2e", plan_version=1, status="committed",
            proof_policy="sprout-1",
            nodes=(
                NodeSpec(
                    "pilot", "implementation", "Pilot", "prove one path", "worker",
                    verification_policy="deterministic", closes_proofs=("pilot",),
                    estimated_execution_ms=20_000,
                ),
                NodeSpec(
                    "branch-a", "implementation", "Branch A", "run A", "worker",
                    verification_policy="deterministic", requires_proofs=("pilot",),
                    closes_proofs=("branch-a",), estimated_execution_ms=90_000,
                ),
                NodeSpec(
                    "branch-b", "implementation", "Branch B", "run B", "worker",
                    verification_policy="deterministic", requires_proofs=("pilot",),
                    closes_proofs=("branch-b",), estimated_execution_ms=80_000,
                ),
                NodeSpec(
                    "verify", "verification", "Fan-in", "verify branches", "verifier",
                    dependencies=("branch-a", "branch-b"),
                    requires_proofs=("branch-a", "branch-b"),
                    closes_proofs=("synthesis",), estimated_execution_ms=30_000,
                ),
                NodeSpec(
                    "commit", "implementation", "Commit", "commit result", "worker",
                    verification_policy="deterministic",
                    dependencies=("verify",), requires_proofs=("synthesis",),
                    estimated_execution_ms=10_000, external_effect=True,
                    reversibility="reversible",
                ),
            ),
        )
        engine = GraphExecutionEngine(
            adapter=adapter, plan_factory=lambda _spec: plan,
            scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
        )

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            self.assertEqual(adapter.started, ["pilot"])
            await engine.advance(handle.run_id)
            self.assertEqual(adapter.started, ["pilot", "branch-a", "branch-b"])
            await engine.advance(handle.run_id)
            self.assertEqual(adapter.started[-1], "verify")
            await engine.advance(handle.run_id)
            self.assertEqual(adapter.started[-1], "commit")
            self.assertEqual(engine.snapshot(handle.run_id).terminal_status, "succeeded")

        asyncio.run(scenario())

    def test_worker_finished_does_not_equal_independent_verification(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-unverified", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "implement", "implementation", "Implement", "implement", "worker",
                verification_policy="independent", estimated_execution_ms=10_000,
            ),),
        )
        engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.node_states["implement"], "awaiting_verification")
            self.assertIsNone(snapshot.terminal_status)

        asyncio.run(scenario())

    def test_independent_verifier_passes_its_awaiting_target_with_wip_one(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-independent", plan_version=1, status="committed",
            nodes=(
                NodeSpec(
                    "implement", "implementation", "Implement", "implement", "worker",
                    verification_policy="independent", estimated_execution_ms=60_000,
                ),
                NodeSpec(
                    "verify", "verification", "Verify", "verify implementation", "verifier",
                    dependencies=("implement",), verification_policy="independent",
                    estimated_execution_ms=30_000,
                ),
            ),
        )
        engine = GraphExecutionEngine(
            adapter=adapter,
            plan_factory=lambda _spec: plan,
            scheduler=Scheduler(SchedulerPolicy(max_wip=1)),
        )

        async def scenario():
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            self.assertEqual(
                engine.snapshot(handle.run_id).node_states["implement"],
                "awaiting_verification",
            )
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.node_states["implement"], "passed")
            self.assertEqual(snapshot.node_states["verify"], "passed")
            self.assertEqual(snapshot.terminal_status, "succeeded")
            self.assertEqual(
                {engine.snapshot(handle.run_id).projection_digest for _ in range(10)},
                {snapshot.projection_digest},
            )

        asyncio.run(scenario())

    def test_runtime_lifecycle_is_canonical_journal_and_replays_in_new_engine(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-restart", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "implement", "implementation", "Implement", "implement", "worker",
                verification_policy="independent", estimated_execution_ms=10_000,
            ),),
        )

        async def scenario():
            first = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await first.start(spec(self.workspace))
            await first.advance(handle.run_id)
            before = first.snapshot(handle.run_id)
            self.assertEqual(before.node_states["implement"], "awaiting_verification")
            first.close(handle.run_id)

            restarted = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            restored = await restarted.start(spec(self.workspace))
            after = restarted.snapshot(restored.run_id)
            self.assertEqual(after.node_states, before.node_states)
            self.assertEqual(after.projection_digest, before.projection_digest)
            self.assertEqual(after.attempt_states, before.attempt_states)

        asyncio.run(scenario())
        journal = self.workspace / ".graphori" / "runs" / "run-restart" / "journal" / "journal.jsonl"
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertIn("attempt_dispatched", [event["type"] for event in events])
        self.assertIn("worker_finished", [event["type"] for event in events])

    def test_skill_binding_projection_replays_and_changed_plan_fails_closed(self):
        binding = SkillBinding(
            skill_id="ponytail", name="ponytail", digest="sha256:abc",
            snapshot_path=".graphori/skills/abc/SKILL.md", source_commit="abc123",
            arguments=(("mode", "full"),), reason="explicit_request",
            activation_scope=ActivationScope.ATTEMPT,
        )
        node = NodeSpec(
            "implement", "implementation", "Implement", "implement", "worker",
            skill_bindings=(binding,),
        )
        plan = RunPlan(
            run_id="run-skill-replay", plan_version=1, status="committed", nodes=(node,),
        )

        async def scenario():
            first = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            handle = await first.start(spec(self.workspace))
            before = first.snapshot(handle.run_id)
            self.assertEqual(before.skill_bindings["implement"][0]["skill_id"], "ponytail")
            first.close(handle.run_id)

            restarted = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            restored = await restarted.start(spec(self.workspace))
            after = restarted.snapshot(restored.run_id)
            self.assertEqual(after.skill_bindings, before.skill_bindings)
            self.assertEqual(after.projection_digest, before.projection_digest)
            restarted.close(restored.run_id)

            changed = RunPlan(
                run_id=plan.run_id, plan_version=1, status="committed",
                nodes=(NodeSpec(
                    "implement", "implementation", "Implement", "implement", "worker",
                ),),
            )
            rejected = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: changed,
            )
            with self.assertRaisesRegex(StateTransitionError, "plan digest"):
                await rejected.start(spec(self.workspace))

        asyncio.run(scenario())

    def test_duplicate_runtime_delivery_is_idempotent_and_conflict_fails_closed(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-duplicate-runtime", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "research", "A", "read", "worker"),),
        )

        async def scenario():
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            event = RuntimeEvent(
                "heartbeat", "a", "worker", {"note": "same"},
                event_id="runtime-heartbeat-1", producer_event_id="worker-a:heartbeat:1",
            )
            await engine.advance(handle.run_id, (event, event))
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(
                [item.event_type for item in snapshot.events].count("heartbeat"), 1,
            )
            conflict = RuntimeEvent(
                "heartbeat", "a", "worker", {"note": "different"},
                event_id="runtime-heartbeat-1", producer_event_id="worker-a:heartbeat:1",
            )
            with self.assertRaises(StateTransitionError):
                await engine.advance(handle.run_id, (conflict,))

        asyncio.run(scenario())

    def test_restart_marks_inflight_attempt_unknown_without_redispatch(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-inflight", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "research", "A", "read", "worker"),),
        )

        async def scenario():
            first = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await first.start(spec(self.workspace))
            await first.advance(handle.run_id, (
                RuntimeEvent(
                    "node_status_changed", "a", "worker", {"status": "ready"},
                    event_id="inflight-ready", producer_event_id="scheduler:a:ready",
                ),
                RuntimeEvent(
                    "attempt_dispatched", "a", "scheduler",
                    {"attempt_id": "attempt:a:1"},
                    event_id="inflight-dispatched", producer_event_id="scheduler:a:dispatch:1",
                ),
                RuntimeEvent(
                    "node_status_changed", "a", "worker",
                    {"status": "running", "attempt_id": "attempt:a:1"},
                    event_id="inflight-running", producer_event_id="worker:a:running:1",
                ),
            ))
            first.close(handle.run_id)

            restarted_adapter = ConcurrentFakeAdapter()
            restarted = GraphExecutionEngine(
                adapter=restarted_adapter, plan_factory=lambda _spec: plan,
            )
            restored = await restarted.start(spec(self.workspace))
            snapshot = restarted.snapshot(restored.run_id)
            self.assertEqual(snapshot.node_states["a"], "outcome_unknown")
            self.assertEqual(snapshot.attempt_states["attempt:a:1"], "outcome_unknown")
            self.assertEqual(restarted_adapter.started, [])

        asyncio.run(scenario())

    def test_worker_cannot_publish_verdict_or_pass_itself(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-actor-truth", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "implementation", "A", "build", "worker"),),
        )

        async def scenario():
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            forged = RuntimeEvent(
                "verdict_recorded", "a", "worker",
                {"verdict": "pass", "evidence_ids": ["ev"]},
                event_id="forged-verdict", producer_event_id="worker:a:verdict",
            )
            with self.assertRaises(StateTransitionError):
                await engine.advance(handle.run_id, (forged,))

        asyncio.run(scenario())

    def test_verifier_cannot_judge_an_unassigned_worker(self):
        adapter = ConcurrentFakeAdapter()
        plan = RunPlan(
            run_id="run-verifier-scope", plan_version=1, status="committed",
            nodes=(
                NodeSpec("a", "implementation", "A", "build A", "worker",
                         verification_policy="independent",
                         estimated_execution_ms=90_000),
                NodeSpec("b", "implementation", "B", "build B", "worker",
                         verification_policy="independent",
                         estimated_execution_ms=80_000),
                NodeSpec("verify", "verification", "Verify A", "review A", "verifier",
                         dependencies=("a",), verification_policy="independent"),
            ),
        )

        async def scenario():
            engine = GraphExecutionEngine(
                adapter=adapter, plan_factory=lambda _spec: plan,
                scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
            )
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            forged = RuntimeEvent(
                "verdict_recorded", "verify", "verifier",
                {
                    "verdict": "pass", "evidence_ids": ["ev-forged"],
                    "target_node_ids": ["b"],
                    "target_attempt_ids": {"b": "attempt:b:1"},
                },
                event_id="forged-target", producer_event_id="verifier:verify:forged",
            )
            with self.assertRaises(StateTransitionError):
                await engine.advance(handle.run_id, (forged,))

        asyncio.run(scenario())

    def test_retry_is_one_new_attempt_and_replays_deterministically(self):
        adapter = RetryOnceAdapter()
        plan = RunPlan(
            run_id="run-retry", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "a", "implementation", "A", "build", "worker",
                verification_policy="deterministic",
            ),),
        )

        async def scenario():
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.node_states["a"], "passed")
            self.assertEqual(snapshot.retry_counts, {"a": 1})
            self.assertEqual(snapshot.attempt_states, {
                "attempt:a:1": "outcome_unknown",
                "attempt:a:2": "succeeded",
            })
            self.assertEqual(snapshot.terminal_status, "succeeded")
            retry_events = [
                event for event in snapshot.events
                if event.event_type == "attempt_dispatched"
            ]
            self.assertEqual(retry_events[-1].payload["retry_of"], "attempt:a:1")

            restarted = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            restored = await restarted.start(spec(self.workspace))
            replayed = restarted.snapshot(restored.run_id)
            self.assertEqual(replayed.projection_digest, snapshot.projection_digest)
            self.assertEqual(replayed.retry_counts, {"a": 1})

        asyncio.run(scenario())

    def test_post_dispatch_outcome_unknown_is_not_retried(self):
        adapter = OutcomeUnknownAdapter()
        plan = RunPlan(
            run_id="run-post-dispatch-unknown", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "a", "implementation", "A", "build", "worker",
                verification_policy="deterministic",
            ),),
        )

        async def scenario():
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(adapter.started, ["a"])
            self.assertEqual(snapshot.node_states["a"], "outcome_unknown")
            self.assertEqual(snapshot.retry_counts, {})
            self.assertEqual(snapshot.attempt_states, {
                "attempt:a:1": "outcome_unknown",
            })
            self.assertIsNone(snapshot.terminal_status)

        asyncio.run(scenario())

    def test_fan_in_releases_exactly_once_after_restart(self):
        plan = RunPlan(
            run_id="run-fan-in-restart", plan_version=1, status="committed",
            nodes=(
                NodeSpec("a", "research", "A", "read A", "worker",
                         verification_policy="deterministic",
                         estimated_execution_ms=90_000),
                NodeSpec("b", "research", "B", "read B", "worker",
                         verification_policy="deterministic",
                         estimated_execution_ms=80_000),
                NodeSpec("verify", "verification", "Verify", "fan in", "verifier",
                         dependencies=("a", "b"), verification_policy="independent"),
            ),
        )

        async def scenario():
            first = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
                scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
            )
            handle = await first.start(spec(self.workspace))
            await first.advance(handle.run_id)
            self.assertEqual(first.snapshot(handle.run_id).node_states["verify"], "pending")
            first.close(handle.run_id)

            adapter = ConcurrentFakeAdapter()
            restarted = GraphExecutionEngine(
                adapter=adapter, plan_factory=lambda _spec: plan,
                scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
            )
            restored = await restarted.start(spec(self.workspace))
            await restarted.advance(restored.run_id)
            await restarted.advance(restored.run_id)
            self.assertEqual(adapter.started, ["verify"])
            self.assertEqual(restarted.snapshot(restored.run_id).terminal_status, "succeeded")

        asyncio.run(scenario())

    def test_terminal_restart_never_dispatches_or_reopens(self):
        plan = RunPlan(
            run_id="run-terminal-restart", plan_version=1, status="committed",
            nodes=(NodeSpec(
                "a", "research", "A", "read", "worker",
                verification_policy="deterministic",
            ),),
        )

        async def scenario():
            first = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            handle = await first.start(spec(self.workspace))
            await first.advance(handle.run_id)
            terminal = first.snapshot(handle.run_id)

            adapter = ConcurrentFakeAdapter()
            restarted = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            restored = await restarted.start(spec(self.workspace))
            result = await restarted.advance(restored.run_id)
            self.assertEqual(result.scheduling.dispatches, ())
            self.assertEqual(adapter.started, [])
            self.assertEqual(adapter.closed_runs, [plan.run_id])
            self.assertEqual(
                restarted.snapshot(restored.run_id).projection_digest,
                terminal.projection_digest,
            )
            with self.assertRaises(StateTransitionError):
                await restarted.advance(restored.run_id, (
                    RuntimeEvent(
                        "heartbeat", "a", "worker", {},
                        event_id="late-heartbeat",
                        producer_event_id="worker:a:late",
                    ),
                ))

        asyncio.run(scenario())

    def test_restart_after_verdict_before_terminal_does_not_rerun_verifier(self):
        plan = RunPlan(
            run_id="run-verdict-crash", plan_version=1, status="committed",
            nodes=(
                NodeSpec("work", "implementation", "Work", "build", "worker",
                         verification_policy="independent"),
                NodeSpec("verify", "verification", "Verify", "review", "verifier",
                         dependencies=("work",), verification_policy="independent"),
            ),
        )

        async def scenario():
            first = GraphExecutionEngine(
                adapter=ConcurrentFakeAdapter(), plan_factory=lambda _spec: plan,
            )
            handle = await first.start(spec(self.workspace))
            await first.advance(handle.run_id)
            await first.advance(handle.run_id)

            journal = (self.workspace / ".graphori" / "runs" / plan.run_id
                       / "journal" / "journal.jsonl")
            lines = journal.read_bytes().splitlines(keepends=True)
            self.assertIn(b'"type":"run_terminal"', lines[-1])
            journal.write_bytes(b"".join(lines[:-1]))

            adapter = ConcurrentFakeAdapter()
            restarted = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            restored = await restarted.start(spec(self.workspace))
            before_settle = restarted.snapshot(restored.run_id)
            self.assertEqual(before_settle.node_states, {"work": "passed", "verify": "passed"})
            self.assertIsNone(before_settle.terminal_status)
            await restarted.advance(restored.run_id)
            self.assertEqual(adapter.started, [])
            self.assertEqual(restarted.snapshot(restored.run_id).terminal_status, "succeeded")

        asyncio.run(scenario())

    def test_rework_creates_one_immutable_revision_and_replays(self):
        plan = RunPlan(
            run_id="run-rework", plan_version=1, status="committed",
            nodes=(
                NodeSpec("work", "implementation", "Work", "build", "worker",
                         verification_policy="independent", closes_proofs=("work",),
                         model="model"),
                NodeSpec("verify", "verification", "Verify", "review", "verifier",
                         dependencies=("work",), closes_proofs=("review",),
                         verification_policy="independent"),
            ),
        )

        async def scenario():
            adapter = ReviseOnceAdapter(self.workspace)
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            for _ in range(4):
                await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            self.assertEqual(snapshot.rework_counts, {"work": 1})
            self.assertEqual(snapshot.node_states["work"], "failed")
            self.assertEqual(snapshot.node_states["work:rework:1"], "passed")
            self.assertEqual(snapshot.node_states["verify:rework:1"], "passed")
            self.assertEqual(snapshot.terminal_status, "succeeded")
            self.assertEqual(adapter.started, [
                "work", "verify", "work:rework:1", "verify:rework:1",
            ])
            continuation = adapter.contexts["work:rework:1"].continuation
            self.assertIsNotNone(continuation)
            self.assertEqual(continuation.handle.opaque_id, "a" * 32)
            self.assertEqual(continuation.nack.proof_ids, ("AC-01",))
            self.assertEqual(
                continuation.nack.command, ("python", "-m", "unittest"),
            )

            restarted = GraphExecutionEngine(
                adapter=ReviseOnceAdapter(self.workspace), plan_factory=lambda _spec: plan,
            )
            restored = await restarted.start(spec(self.workspace))
            replayed = restarted.snapshot(restored.run_id)
            self.assertEqual(replayed.projection_digest, snapshot.projection_digest)
            self.assertEqual(replayed.rework_counts, {"work": 1})

        asyncio.run(scenario())

    def test_rework_keeps_nack_when_provider_session_is_not_eligible(self):
        class ModelMismatchAdapter(ReviseOnceAdapter):
            async def events(self, dispatch):
                async for event in super().events(dispatch):
                    if event.node_id == "work" and event.event_type == "worker_finished":
                        payload = dict(event.payload)
                        metadata = dict(payload["runtime_metadata"])
                        session = dict(metadata["provider_session"])
                        session["observed_model"] = "different-model"
                        metadata["provider_session"] = session
                        payload["runtime_metadata"] = metadata
                        event = RuntimeEvent(
                            event.event_type, event.node_id, event.actor_role, payload,
                            event.event_id, event.producer_event_id,
                            event.actor_role_id, event.occurred_at,
                        )
                    yield event

        plan = RunPlan(
            run_id="run-fresh-repair-nack", plan_version=1, status="committed",
            nodes=(
                NodeSpec(
                    "work", "implementation", "Work", "build", "worker",
                    verification_policy="independent", closes_proofs=("work",),
                    model="model",
                ),
                NodeSpec(
                    "verify", "verification", "Verify", "review", "verifier",
                    dependencies=("work",), closes_proofs=("review",),
                    verification_policy="independent",
                ),
            ),
        )

        async def scenario():
            adapter = ModelMismatchAdapter(self.workspace)
            engine = GraphExecutionEngine(adapter=adapter, plan_factory=lambda _spec: plan)
            handle = await engine.start(spec(self.workspace))
            await engine.advance(handle.run_id)
            await engine.advance(handle.run_id)
            await engine.advance(handle.run_id)
            continuation = adapter.contexts["work:rework:1"].continuation
            self.assertIsNotNone(continuation)
            self.assertIsNone(continuation.handle)
            self.assertEqual(continuation.nack.proof_ids, ("AC-01",))
            self.assertEqual(
                continuation.nack.command, ("python", "-m", "unittest"),
            )

        asyncio.run(scenario())

    def test_retry_and_rework_exhaustion_do_not_loop(self):
        retry_plan = RunPlan(
            run_id="run-retry-exhausted", plan_version=1, status="committed",
            nodes=(NodeSpec("a", "implementation", "A", "build", "worker"),),
        )
        rework_plan = RunPlan(
            run_id="run-rework-exhausted", plan_version=1, status="committed",
            nodes=(
                NodeSpec("work", "implementation", "Work", "build", "worker",
                         verification_policy="independent"),
                NodeSpec("verify", "verification", "Verify", "review", "verifier",
                         dependencies=("work",), verification_policy="independent"),
            ),
        )

        async def scenario():
            retry_adapter = AlwaysTimeoutAdapter()
            retry_engine = GraphExecutionEngine(
                adapter=retry_adapter, plan_factory=lambda _spec: retry_plan,
            )
            retry_handle = await retry_engine.start(spec(self.workspace))
            await retry_engine.advance(retry_handle.run_id)
            retry_snapshot = retry_engine.snapshot(retry_handle.run_id)
            self.assertEqual(retry_adapter.started, ["a", "a"])
            self.assertEqual(retry_snapshot.retry_counts, {"a": 1})
            self.assertEqual(retry_snapshot.terminal_status, "blocked")

            rework_adapter = AlwaysReviseAdapter()
            rework_engine = GraphExecutionEngine(
                adapter=rework_adapter, plan_factory=lambda _spec: rework_plan,
            )
            rework_handle = await rework_engine.start(spec(self.workspace))
            for _ in range(4):
                await rework_engine.advance(rework_handle.run_id)
            rework_snapshot = rework_engine.snapshot(rework_handle.run_id)
            self.assertEqual(rework_snapshot.rework_counts, {"work": 1})
            self.assertEqual(len(rework_snapshot.open_gates), 1)
            self.assertIsNone(rework_snapshot.terminal_status)
            await rework_engine.advance(rework_handle.run_id)
            self.assertEqual(rework_adapter.started, [
                "work", "verify", "work:rework:1", "verify:rework:1",
            ])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
