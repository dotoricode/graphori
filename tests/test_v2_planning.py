import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    PlanEdge, RunConstraints, RunPlan, RunSpec, NodeSpec, PremiumPolicy,
    TeamSpec,
)


class V2PlanningContractTests(unittest.TestCase):
    def test_run_spec_has_deterministic_round_trip_and_digest(self):
        spec = RunSpec(
            objective="Build and verify two independent readers",
            host="codex",
            workspace="/workspace",
            constraints=RunConstraints(max_parallelism=2, allow_network=False),
            premium_policy=PremiumPolicy(requires_approval=("tier:frontier",)),
            runtime_preference=("native_host", "orca", "generic_process"),
        )
        encoded = spec.canonical_json()
        restored = RunSpec.from_dict(json.loads(encoded))
        self.assertEqual(restored, spec)
        self.assertEqual(restored.digest(), spec.digest())
        self.assertEqual(encoded, restored.canonical_json())

    def test_run_spec_omitted_optional_fields_preserve_contract_defaults(self):
        restored = RunSpec.from_dict({
            "objective": "small task", "host": "codex", "workspace": "/workspace",
        })
        self.assertEqual(restored, RunSpec("small task", "codex", "/workspace"))
        self.assertTrue(restored.premium_policy.requires_approval)
        self.assertTrue(restored.runtime_preference)

    def test_stable_acceptance_criteria_round_trip_into_node_spec(self):
        spec = RunSpec(
            "small task", "codex", "/workspace",
            acceptance_criteria=("AC-01: completes safely",),
        )
        restored = RunSpec.from_dict(spec.to_dict())
        node = NodeSpec("work", "implementation", "요청한 변경 구현", "work", "worker",
                        acceptance_criteria=restored.acceptance_criteria)
        self.assertEqual(restored.acceptance_criteria, ("AC-01: completes safely",))
        self.assertEqual(node.acceptance_criteria, restored.acceptance_criteria)
        with self.assertRaises(ValueError):
            RunSpec("bad", "codex", "/workspace", acceptance_criteria=("no stable id",))

    def test_run_spec_rejects_non_finite_or_negative_budgets(self):
        for value in (float("nan"), float("inf"), -1.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RunConstraints(cost_budget_usd=value)
        with self.assertRaises(ValueError):
            RunConstraints(time_budget_ms=-1)

    def test_run_plan_serialization_is_order_independent_for_graph_members(self):
        node_a = NodeSpec(
            node_id="read-a", team_id="research", title="Read A",
            objective="Read source A", kind="worker", read_scope=("src/a.py",),
            estimated_execution_ms=90_000,
        )
        node_b = NodeSpec(
            node_id="read-b", team_id="research", title="Read B",
            objective="Read source B", kind="worker", read_scope=("src/b.py",),
            estimated_execution_ms=80_000,
        )
        common = dict(
            run_id="run-v2", plan_version=1, status="committed",
            teams=(TeamSpec("research", "active"), TeamSpec("planning", "active")),
            critical_path=("read-a",),
        )
        first = RunPlan(nodes=(node_a, node_b), edges=(PlanEdge("read-a", "read-b"),), **common)
        second = RunPlan(nodes=(node_b, node_a), edges=(PlanEdge("read-a", "read-b"),),
                         teams=tuple(reversed(common["teams"])),
                         run_id="run-v2", plan_version=1, status="committed",
                         critical_path=("read-a",))
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(RunPlan.from_dict(first.to_dict()), first)

    def test_unknown_or_unsupported_plan_fields_fail_closed(self):
        plan = RunPlan(run_id="run-v2", plan_version=1, status="provisional")
        data = plan.to_dict()
        data["surprise"] = True
        with self.assertRaises(ValueError):
            RunPlan.from_dict(data)
        data = plan.to_dict()
        data["schema_version"] = 99
        with self.assertRaises(ValueError):
            RunPlan.from_dict(data)

    def test_plan_rejects_unknown_team_and_dependency(self):
        with self.assertRaises(ValueError):
            TeamSpec("made-up-team", "active")
        with self.assertRaises(ValueError):
            RunPlan(
                run_id="run-bad", plan_version=1, status="committed",
                nodes=(NodeSpec(
                    node_id="worker", team_id="implementation", title="Worker",
                    objective="work", kind="worker", dependencies=("missing",),
                ),),
            )

    def test_plan_rejects_dependency_cycles(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            RunPlan(
                run_id="run-cycle", plan_version=1, status="committed",
                nodes=(
                    NodeSpec("a", "design", "A", "A", "worker",
                             dependencies=("b",)),
                    NodeSpec("b", "implementation", "B", "B", "worker",
                             dependencies=("a",)),
                ),
            )


if __name__ == "__main__":
    unittest.main()
