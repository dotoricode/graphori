import asyncio
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    AdapterCapabilities,
    ApprovalClass,
    ContextBundle,
    DispatchHandle,
    ExecutionResult,
    GraphExecutionEngine,
    NodeSpec,
    PremiumApprovalEnvelope,
    RouteTarget,
    RunConstraints,
    RunPlan,
    RunSpec,
    RuntimeEvent,
    RuntimeRunHandle,
    Scheduler,
    SchedulerPolicy,
    SessionHandle,
    StateTransitionError,
)


class RoutingAwareFakeAdapter:
    adapter_id = "routing-fake"

    def __init__(self):
        self.started = []

    def probe(self):
        return AdapterCapabilities(self.adapter_id, True, max_concurrency=3)

    async def prepare_run(self, plan):
        return RuntimeRunHandle(self.adapter_id, plan.run_id)

    async def start_session(self, node):
        self.started.append((node.node_id, node.model, node.effort))
        return SessionHandle(self.adapter_id, f"session:{node.node_id}")

    async def dispatch(self, session, node, context: ContextBundle):
        return DispatchHandle(self.adapter_id, f"dispatch:{node.node_id}", node.node_id)

    async def events(self, dispatch):
        yield RuntimeEvent(
            "worker_finished", dispatch.node_id, "worker", {"outcome": "succeeded"},
        )

    async def cancel(self, dispatch, reason):
        return None

    async def collect(self, dispatch):
        return ExecutionResult("succeeded", runtime_id=dispatch.value)

    async def release(self, session):
        return None


class RevisingRoutingAdapter(RoutingAwareFakeAdapter):
    async def events(self, dispatch):
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


def premium_node(node_id="premium"):
    return NodeSpec(
        node_id, "design", "Premium", "critical synthesis", "worker",
        read_scope=("src",), write_scope=("src/design.py",),
        provider="codex", provider_family="openai", adapter="codex",
        model="gpt-5.6-sol", model_family="sol", effort="high",
        fallback_provider_family="openai", fallback_adapter="codex",
        fallback_model="gpt-5.6-terra", fallback_model_family="terra",
        fallback_effort="xhigh",
        approval_required=True, approval_class="premium",
        routing_decision_digest="sha256:" + "a" * 64,
        routing_reason_codes=("CRITICAL_SYNTHESIS",),
        verification_policy="deterministic",
        estimated_execution_ms=90_000,
    )


class PremiumApprovalEnvelopeTests(unittest.TestCase):
    def test_approval_scope_allows_effort_decrease_but_not_increase(self):
        node = premium_node()
        envelope = PremiumApprovalEnvelope.for_node("run-premium", 1, node)
        medium = RouteTarget(
            "openai", "codex", "gpt-5.6-sol", "sol", "medium",
            ApprovalClass.PREMIUM,
        )
        xhigh = RouteTarget(
            "openai", "codex", "gpt-5.6-sol", "sol", "xhigh",
            ApprovalClass.PREMIUM,
        )
        self.assertTrue(envelope.covers("run-premium", 1, node, medium))
        self.assertFalse(envelope.covers("run-premium", 1, node, xhigh))

    def test_scope_or_permission_expansion_invalidates_approval(self):
        node = premium_node()
        envelope = PremiumApprovalEnvelope.for_node("run-premium", 1, node)
        widened = NodeSpec(
            **{**node.__dict__, "write_scope": ("src",)}
        )
        target = RouteTarget(
            "openai", "codex", "gpt-5.6-sol", "sol", "high",
            ApprovalClass.PREMIUM,
        )
        self.assertFalse(envelope.covers("run-premium", 1, widened, target))


class PremiumGateEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.adapter = RoutingAwareFakeAdapter()

    def plan(self):
        return RunPlan(
            "run-premium", 1, "committed",
            nodes=(
                NodeSpec(
                    "safe-a", "research", "Safe A", "read", "worker",
                    read_scope=("docs/a",), model="gpt-5.6-luna", effort="medium",
                    verification_policy="deterministic", estimated_execution_ms=90_000,
                ),
                premium_node(),
                NodeSpec(
                    "safe-c", "implementation", "Safe C", "work", "worker",
                    read_scope=("docs/c",), model="gpt-5.6-terra", effort="high",
                    verification_policy="deterministic", estimated_execution_ms=80_000,
                ),
            ),
        )

    def engine(self, adapter=None):
        return GraphExecutionEngine(
            adapter=adapter or self.adapter,
            plan_factory=lambda _spec: self.plan(),
            scheduler=Scheduler(SchedulerPolicy(max_wip=3)),
        )

    def spec(self):
        return RunSpec(
            "premium fixture", "test", str(self.workspace),
            constraints=RunConstraints(max_parallelism=3),
        )

    def test_unapproved_node_never_reaches_adapter_while_independent_nodes_continue(self):
        engine = self.engine()

        async def scenario():
            handle = await engine.start(self.spec())
            initial = engine.snapshot(handle.run_id)
            self.assertEqual(len(initial.open_gates), 1)
            batch = await engine.advance(handle.run_id)
            self.assertEqual(
                {item.node_id for item in batch.scheduling.dispatches},
                {"safe-a", "safe-c"},
            )
            self.assertNotIn("premium", {item[0] for item in self.adapter.started})

        asyncio.run(scenario())

    def test_approval_is_idempotent_and_dispatches_exactly_once(self):
        engine = self.engine()

        async def scenario():
            handle = await engine.start(self.spec())
            gate_id = next(iter(engine.snapshot(handle.run_id).open_gates))
            envelope = PremiumApprovalEnvelope.for_node(
                handle.run_id, 1, premium_node(),
            )
            await engine.resolve_premium_gate(handle.run_id, gate_id, "approve", envelope)
            await engine.resolve_premium_gate(handle.run_id, gate_id, "approve", envelope)
            await engine.advance(handle.run_id)
            await engine.advance(handle.run_id)

        asyncio.run(scenario())
        self.assertEqual([item[0] for item in self.adapter.started].count("premium"), 1)

    def test_use_fallback_dispatches_precomputed_nonpremium_route(self):
        engine = self.engine()

        async def scenario():
            handle = await engine.start(self.spec())
            gate_id = next(iter(engine.snapshot(handle.run_id).open_gates))
            await engine.resolve_premium_gate(handle.run_id, gate_id, "use_fallback")
            await engine.advance(handle.run_id)

        asyncio.run(scenario())
        premium = next(item for item in self.adapter.started if item[0] == "premium")
        self.assertEqual(premium[1:], ("gpt-5.6-terra", "xhigh"))
        observed = [
            event for event in engine.snapshot("run-premium").events
            if event.event_type == "routing_observed" and event.node_id == "premium"
        ][0]
        self.assertEqual(observed.payload["requested_model"], "gpt-5.6-terra")
        self.assertEqual(observed.payload["requested_effort"], "xhigh")
        self.assertEqual(observed.payload["observed_model"], "")

    def test_gate_replays_and_late_approval_after_cancel_cannot_dispatch(self):
        first = self.engine()

        async def scenario():
            handle = await first.start(self.spec())
            gate_id = next(iter(first.snapshot(handle.run_id).open_gates))
            await first.cancel(handle.run_id, "stop")

            restarted_adapter = RoutingAwareFakeAdapter()
            restarted = self.engine(restarted_adapter)
            await restarted.start(self.spec())
            self.assertFalse(restarted.snapshot(handle.run_id).open_gates)
            with self.assertRaises(StateTransitionError):
                await restarted.resolve_premium_gate(
                    handle.run_id, gate_id, "approve",
                    PremiumApprovalEnvelope.for_node(handle.run_id, 1, premium_node()),
                )
            self.assertNotIn("premium", {item[0] for item in restarted_adapter.started})

        asyncio.run(scenario())

    def test_skip_closes_gate_without_dispatching_premium_node(self):
        engine = self.engine()

        async def scenario():
            handle = await engine.start(self.spec())
            gate_id = next(iter(engine.snapshot(handle.run_id).open_gates))
            await engine.resolve_premium_gate(handle.run_id, gate_id, "skip")
            await engine.advance(handle.run_id)
            self.assertEqual(
                engine.snapshot(handle.run_id).node_states["premium"], "cancelled",
            )

        asyncio.run(scenario())
        self.assertNotIn("premium", {item[0] for item in self.adapter.started})

    def test_premium_fallback_cannot_bypass_a_second_gate(self):
        plan = self.plan()
        premium = premium_node()
        premium = NodeSpec(**{
            **premium.__dict__, "fallback_approval_class": "premium",
        })
        plan = RunPlan(
            plan.run_id, plan.plan_version, plan.status,
            nodes=tuple(premium if item.node_id == "premium" else item for item in plan.nodes),
        )
        engine = GraphExecutionEngine(
            adapter=self.adapter, plan_factory=lambda _spec: plan,
        )

        async def scenario():
            handle = await engine.start(self.spec())
            gate_id = next(iter(engine.snapshot(handle.run_id).open_gates))
            with self.assertRaises(StateTransitionError):
                await engine.resolve_premium_gate(handle.run_id, gate_id, "use_fallback")

        asyncio.run(scenario())

    def test_rework_of_premium_node_requires_a_new_node_local_gate(self):
        plan = RunPlan(
            "run-premium", 1, "committed",
            nodes=(
                NodeSpec(**{
                    **premium_node().__dict__,
                    "verification_policy": "independent",
                }),
                NodeSpec(
                    "verify", "verification", "Verify", "review", "verifier",
                    dependencies=("premium",), verification_policy="independent",
                ),
            ),
        )
        adapter = RevisingRoutingAdapter()
        engine = GraphExecutionEngine(
            adapter=adapter, plan_factory=lambda _spec: plan,
            scheduler=Scheduler(SchedulerPolicy(max_wip=2)),
        )

        async def scenario():
            handle = await engine.start(self.spec())
            first_gate = next(iter(engine.snapshot(handle.run_id).open_gates))
            await engine.resolve_premium_gate(
                handle.run_id, first_gate, "approve",
                PremiumApprovalEnvelope.for_node(handle.run_id, 1, plan.nodes[0]),
            )
            await engine.advance(handle.run_id)
            await engine.advance(handle.run_id)
            snapshot = engine.snapshot(handle.run_id)
            premium_gates = [
                gate for gate in snapshot.open_gates
                if snapshot.gate_records[gate]["kind"] == "premium_model"
            ]
            self.assertEqual(len(premium_gates), 1)
            self.assertEqual(
                snapshot.gate_records[premium_gates[0]]["approval_envelope"]["node_id"],
                "premium:rework:1",
            )
            await engine.advance(handle.run_id)

        asyncio.run(scenario())
        self.assertEqual([item[0] for item in adapter.started], ["premium", "verify"])


if __name__ == "__main__":
    unittest.main()
