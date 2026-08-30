import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    NodeSpec, RunPlan, Scheduler, SchedulerPolicy, SchedulingState,
)


def node(node_id, *, deps=(), read=(), write=(), execution=90_000,
         startup=0, approval=False, team="implementation", kind="worker",
         requires_proofs=(), closes_proofs=()):
    return NodeSpec(
        node_id=node_id, team_id=team, title=node_id, objective=node_id,
        kind=kind, dependencies=deps, read_scope=read, write_scope=write,
        estimated_execution_ms=execution, estimated_startup_ms=startup,
        approval_required=approval, requires_proofs=requires_proofs,
        closes_proofs=closes_proofs,
    )


class V2SchedulerContractTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler(SchedulerPolicy(max_wip=2))

    def plan(self, *nodes):
        return RunPlan(run_id="run-schedule", plan_version=1,
                       status="committed", nodes=nodes)

    def test_independent_read_only_work_dispatches_in_parallel_when_profitable(self):
        plan = self.plan(
            node("research-a", read=("docs/a",), execution=90_000, team="research"),
            node("research-b", read=("docs/b",), execution=80_000, team="research"),
        )
        batch = self.scheduler.decide(plan, SchedulingState())
        self.assertEqual(tuple(item.node_id for item in batch.dispatches),
                         ("research-a", "research-b"))
        self.assertGreaterEqual(batch.estimated_parallel_gain_ms, 30_000)

    def test_shared_write_scope_is_serialized(self):
        plan = self.plan(
            node("a", write=("src/shared.py",)),
            node("b", write=("src/shared.py",)),
        )
        batch = self.scheduler.decide(plan, SchedulingState())
        self.assertEqual(len(batch.dispatches), 1)
        self.assertEqual(batch.queued, ("b",))

    def test_parallelism_without_net_gain_is_rejected(self):
        plan = self.plan(
            node("a", read=("a",), execution=10_000, startup=8_000),
            node("b", read=("b",), execution=10_000, startup=8_000),
        )
        batch = self.scheduler.decide(plan, SchedulingState())
        self.assertEqual(tuple(item.node_id for item in batch.dispatches), ("a",))
        self.assertEqual(batch.queued, ("b",))

    def test_fan_in_waits_for_every_dependency(self):
        plan = self.plan(
            node("a"), node("b"), node("verify", deps=("a", "b"), team="verification"),
        )
        batch = self.scheduler.decide(
            plan, SchedulingState(node_states={"a": "passed", "b": "running"}),
        )
        self.assertNotIn("verify", tuple(item.node_id for item in batch.dispatches))
        self.assertIn("verify", batch.waiting)
        batch = self.scheduler.decide(
            plan, SchedulingState(node_states={"a": "passed", "b": "passed"}),
        )
        self.assertEqual(tuple(item.node_id for item in batch.dispatches), ("verify",))

    def test_awaiting_verification_releases_wip_for_its_verifier(self):
        scheduler = Scheduler(SchedulerPolicy(max_wip=1))
        plan = self.plan(
            node("implement", write=("src/feature.py",)),
            node("verify", deps=("implement",), team="verification", kind="verifier"),
        )
        batch = scheduler.decide(
            plan,
            SchedulingState(node_states={"implement": "awaiting_verification"}),
        )
        self.assertEqual(tuple(item.node_id for item in batch.dispatches), ("verify",))
        self.assertNotIn("implement", batch.ready)

    def test_awaiting_verification_releases_a_read_only_reviewer(self):
        scheduler = Scheduler(SchedulerPolicy(max_wip=1))
        plan = self.plan(
            node("implement", write=("src/feature.py",)),
            NodeSpec(
                "review", "verification", "Review", "review", "worker",
                role="reviewer", dependencies=("implement",), read_scope=("src/",),
                verification_policy="deterministic", reviews_unverified_dependencies=True,
            ),
        )
        batch = scheduler.decide(
            plan, SchedulingState(node_states={"implement": "awaiting_verification"}),
        )
        self.assertEqual(tuple(item.node_id for item in batch.dispatches), ("review",))

    def test_premium_gate_blocks_only_its_node(self):
        plan = self.plan(
            node("premium", approval=True, read=("premium",)),
            node("safe", read=("safe",)),
        )
        batch = self.scheduler.decide(plan, SchedulingState())
        self.assertEqual(tuple(item.node_id for item in batch.dispatches), ("safe",))
        self.assertEqual(batch.blocked, ("premium",))

    def test_same_input_produces_same_batch(self):
        plan = self.plan(node("b", read=("b",)), node("a", read=("a",)))
        state = SchedulingState(queue_age_ms={"b": 10_000, "a": 0})
        self.assertEqual(self.scheduler.decide(plan, state),
                         self.scheduler.decide(plan, state))

    def test_proof_gated_node_waits_until_required_proof_passes(self):
        plan = self.plan(
            node("pilot", closes_proofs=("pilot-qualified",)),
            node("branch", requires_proofs=("pilot-qualified",)),
        )
        waiting = self.scheduler.decide(
            plan, SchedulingState(node_states={"pilot": "passed"}),
        )
        self.assertIn("branch", waiting.waiting)
        ready = self.scheduler.decide(
            plan,
            SchedulingState(
                node_states={"pilot": "passed"},
                proof_states={"pilot-qualified": "passed"},
            ),
        )
        self.assertEqual(tuple(item.node_id for item in ready.dispatches), ("branch",))

    def test_failed_or_unknown_proof_blocks_automatic_dispatch(self):
        plan = self.plan(
            node("synthesis", closes_proofs=("synthesis",)),
            node("commit", requires_proofs=("synthesis",)),
        )
        for state in ("failed", "unknown"):
            with self.subTest(state=state):
                batch = self.scheduler.decide(
                    plan, SchedulingState(proof_states={"synthesis": state}),
                )
                self.assertIn("commit", batch.blocked)


if __name__ == "__main__":
    unittest.main()
