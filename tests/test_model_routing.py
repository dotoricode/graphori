import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    ApprovalClass,
    Availability,
    BenchmarkCatalog,
    LocalTelemetrySnapshot,
    ModelBenchmarkBinding,
    ModelCatalog,
    ModelRouter,
    NodeSpec,
    ProviderCatalog,
    RunPlan,
    RoutingMode,
    RoutingDecision,
    RoutingTelemetryRecord,
    RuntimeModel,
    TaskFeatures,
    default_model_catalog,
    load_benchmark_snapshot,
)


def catalog():
    benchmark = load_benchmark_snapshot()
    runtime = (
        RuntimeModel("openai", "codex", "gpt-5.6-luna", "luna",
                     ("medium", "high"), Availability.AVAILABLE,
                     ApprovalClass.NORMAL, ("coding", "research", "design")),
        RuntimeModel("openai", "codex", "gpt-5.6-terra", "terra",
                     ("medium", "high", "xhigh"), Availability.AVAILABLE,
                     ApprovalClass.NORMAL, ("coding", "design", "verification")),
        RuntimeModel("openai", "codex", "gpt-5.6-sol", "sol",
                     ("medium", "high", "xhigh"), Availability.AVAILABLE,
                     ApprovalClass.PREMIUM, ("coding", "design", "verification")),
        RuntimeModel("anthropic", "claude", "claude-sonnet-5", "sonnet",
                     ("medium", "high"), Availability.AVAILABLE,
                     ApprovalClass.NORMAL, ("research", "design", "verification")),
        RuntimeModel("anthropic", "claude", "claude-opus-5", "opus",
                     ("medium", "high", "xhigh"), Availability.AVAILABLE,
                     ApprovalClass.PREMIUM, ("design", "verification")),
    )
    runtime_ids = {
        "luna": "gpt-5.6-luna", "terra": "gpt-5.6-terra",
        "sol": "gpt-5.6-sol", "opus": "claude-opus-5",
    }
    bindings = tuple(
        ModelBenchmarkBinding(
            item.benchmark_model_id, runtime_ids[item.family], item.effort,
            "high" if item.family in {"luna", "terra", "sol"} else "medium",
        )
        for item in benchmark.models
        if item.family in runtime_ids
    )
    return ModelCatalog(ProviderCatalog(runtime), benchmark, bindings)


class ModelRouterContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog()
        self.router = ModelRouter(self.catalog)

    def route(self, task_kind, **changes):
        features = TaskFeatures(
            node_id="node-a", team="implementation", role="worker",
            risk="low", uncertainty=0, scope=1, synthesis=0,
            task_kind=task_kind, read_only=False, write_required=True,
        )
        return self.router.route(replace(features, **changes))

    def test_runtime_and_benchmark_identities_are_separate(self):
        benchmark = self.catalog.benchmark_catalog.models[0]
        runtime = self.catalog.provider_catalog.models[0]
        self.assertNotEqual(benchmark.benchmark_model_id, runtime.runtime_model_id)
        self.assertTrue(self.catalog.benchmark_catalog.snapshot_digest.startswith("sha256:"))

    def test_deterministic_work_uses_no_model(self):
        decision = self.route("deterministic")
        self.assertEqual(decision.primary.runtime_model_id, "")
        self.assertEqual(decision.reason_codes, ("DETERMINISTIC_NO_MODEL",))

    def test_latency_first_profiles_choose_quality_floor_not_highest_score(self):
        routine = self.route("routine")
        bounded = self.route("bounded_implementation")
        general = self.route("general_implementation", scope=3, risk="medium")
        complex_work = self.route(
            "complex_implementation", scope=5, risk="high", uncertainty=3,
        )
        self.assertEqual((routine.primary.family, routine.primary.effort),
                         ("luna", "medium"))
        self.assertEqual((bounded.primary.family, bounded.primary.effort),
                         ("terra", "medium"))
        self.assertEqual((general.primary.family, general.primary.effort),
                         ("terra", "high"))
        self.assertEqual((complex_work.primary.family, complex_work.primary.effort),
                         ("terra", "high"))

    def test_quality_mode_raises_floor_without_bypassing_premium_policy(self):
        decision = ModelRouter(self.catalog, mode=RoutingMode.QUALITY).route(
            TaskFeatures(
                "node-a", "implementation", "worker", "high", 3, 5, 1,
                "complex_implementation", False, True,
            )
        )
        self.assertEqual((decision.primary.family, decision.primary.effort),
                         ("terra", "xhigh"))
        self.assertEqual(decision.primary.approval_class, ApprovalClass.NORMAL)

    def test_critical_synthesis_selects_sol_high_with_nonpremium_fallback(self):
        decision = self.route(
            "critical_synthesis", scope=7, synthesis=3, risk="critical",
            uncertainty=3,
        )
        self.assertEqual((decision.primary.family, decision.primary.effort),
                         ("sol", "high"))
        self.assertEqual(decision.primary.approval_class, ApprovalClass.PREMIUM)
        self.assertEqual((decision.fallbacks[0].family, decision.fallbacks[0].effort),
                         ("terra", "xhigh"))

    def test_cross_provider_verification_is_a_constraint_not_a_bonus(self):
        decision = self.router.route(TaskFeatures(
            "verify", "verification", "verifier", "high", 1, 2, 1,
            "verification", True, False,
            requires_cross_provider=True, excluded_provider="openai",
        ))
        self.assertEqual(decision.primary.provider, "anthropic")
        self.assertEqual(decision.primary.family, "sonnet")
        self.assertIsNone(decision.primary.quality_score)
        self.assertEqual(decision.benchmark_confidence, "partial")

    def test_frontier_cross_provider_synthesis_routes_to_premium_opus_identity(self):
        decision = self.router.route(TaskFeatures(
            "frontier", "design", "worker", "critical", 3, 7, 3,
            "critical_synthesis", True, False,
            requires_cross_provider=True, excluded_provider="openai",
        ))
        self.assertEqual(decision.primary.runtime_model_id, "claude-opus-5")
        self.assertEqual(decision.primary.effort, "xhigh")
        self.assertEqual(decision.primary.approval_class, ApprovalClass.PREMIUM)

    def test_unavailable_primary_uses_precomputed_available_candidate(self):
        models = tuple(
            replace(item, availability=Availability.UNAVAILABLE)
            if item.family == "luna" else item
            for item in self.catalog.provider_catalog.models
        )
        router = ModelRouter(replace(
            self.catalog, provider_catalog=ProviderCatalog(models),
        ))
        decision = router.route(TaskFeatures(
            "routine", "research", "worker", "low", 0, 1, 0,
            "routine", True, False,
        ))
        self.assertNotEqual(decision.primary.family, "luna")
        self.assertIn("PRIMARY_UNAVAILABLE_FALLBACK", decision.reason_codes)

    def test_same_inputs_produce_same_digest_one_hundred_times(self):
        features = TaskFeatures(
            "node-a", "implementation", "worker", "medium", 1, 3, 0,
            "general_implementation", False, True,
        )
        digests = {self.router.route(features).decision_digest for _ in range(100)}
        self.assertEqual(len(digests), 1)

    def test_tampered_routing_decision_digest_is_rejected(self):
        value = self.route("routine").to_dict()
        value["decision_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            RoutingDecision.from_dict(value)

    def test_unknown_benchmark_has_no_fabricated_score(self):
        sonnet = next(
            item for item in self.catalog.candidates()
            if item.runtime.family == "sonnet" and item.effort == "medium"
        )
        self.assertIsNone(sonnet.benchmark)
        self.assertIsNone(sonnet.quality_score)

    def test_snapshot_round_trip_preserves_source_digest(self):
        snapshot = load_benchmark_snapshot()
        encoded = json.dumps(snapshot.to_dict(), sort_keys=True)
        restored = BenchmarkCatalog.from_dict(json.loads(encoded))
        self.assertEqual(restored.snapshot_digest, snapshot.snapshot_digest)
        changed = replace(snapshot, benchmark_version="v1.4")
        self.assertNotEqual(changed.snapshot_digest, snapshot.snapshot_digest)

    def test_cost_is_secondary_when_quality_and_latency_are_equal(self):
        adjusted = []
        for item in self.catalog.benchmark_catalog.models:
            if item.benchmark_model_id == "aa-v1.3-luna-medium":
                adjusted.append(replace(
                    item, expected_wall_ms=200_000, cost_per_task_usd=2.0,
                ))
            elif item.benchmark_model_id == "aa-v1.3-terra-medium":
                adjusted.append(replace(
                    item, expected_wall_ms=200_000, cost_per_task_usd=1.0,
                ))
            else:
                adjusted.append(item)
        custom = replace(
            self.catalog,
            benchmark_catalog=replace(
                self.catalog.benchmark_catalog, models=tuple(adjusted),
            ),
        )
        decision = ModelRouter(custom).route(TaskFeatures(
            "routine", "research", "worker", "low", 0, 1, 0,
            "routine", True, False,
        ))
        self.assertEqual(decision.primary.family, "terra")

    def test_default_catalog_marks_sol_and_opus_premium_without_name_matching(self):
        discovered = default_model_catalog({
            "gpt-5.6-sol": Availability.AVAILABLE,
            "claude-opus-5": Availability.AVAILABLE,
        })
        classes = {
            item.runtime_model_id: item.approval_class
            for item in discovered.provider_catalog.models
        }
        self.assertEqual(classes["gpt-5.6-sol"], ApprovalClass.PREMIUM)
        self.assertEqual(classes["claude-opus-5"], ApprovalClass.PREMIUM)
        terra = next(
            item for item in discovered.provider_catalog.models
            if item.runtime_model_id == "gpt-5.6-terra"
        )
        self.assertEqual(terra.availability, Availability.UNKNOWN)

    def test_local_telemetry_hook_does_not_claim_confidence_from_one_sample(self):
        snapshot = LocalTelemetrySnapshot.from_records((RoutingTelemetryRecord(
            "routing:one", "gpt-5.6-terra", "gpt-5.6-terra", "high", "high",
            10, 20, 30, 60, "succeeded", "pass", False,
        ),))
        self.assertEqual(snapshot.sample_counts["gpt-5.6-terra"], 1)
        self.assertEqual(snapshot.confidence, "unknown")

    def test_task_features_are_extracted_without_an_llm(self):
        bounded = TaskFeatures.from_node(NodeSpec(
            "small", "implementation", "Small", "small change", "worker",
            write_scope=("src/a.py",), risk="low",
        ))
        critical = TaskFeatures.from_node(NodeSpec(
            "critical", "design", "Critical", "synthesize architecture", "worker",
            read_scope=("src",), risk="critical", uncertainty=3, synthesis=3,
        ))
        self.assertEqual(bounded.task_kind, "bounded_implementation")
        self.assertTrue(bounded.write_required)
        self.assertEqual(critical.task_kind, "critical_synthesis")

    def test_route_plan_records_provider_adapter_model_reason_and_fallback(self):
        plan = RunPlan(
            "run-routing", 1, "committed",
            nodes=(
                NodeSpec(
                    "routine", "research", "Routine", "read docs", "worker",
                    read_scope=("docs",), task_kind="routine",
                ),
                NodeSpec(
                    "critical", "design", "Critical", "synthesize", "worker",
                    read_scope=("src",), risk="critical", uncertainty=3,
                    synthesis=3, task_kind="critical_synthesis",
                ),
            ),
        )
        routed = self.router.route_plan(plan)
        nodes = {item.node_id: item for item in routed.nodes}
        self.assertEqual(nodes["routine"].provider_family, "openai")
        self.assertEqual(nodes["routine"].adapter, "codex")
        self.assertEqual(nodes["routine"].model, "gpt-5.6-luna")
        self.assertFalse(nodes["routine"].approval_required)
        self.assertEqual(nodes["critical"].approval_class, "premium")
        self.assertEqual(nodes["critical"].fallback_model, "gpt-5.6-terra")
        self.assertEqual(nodes["critical"].fallback_effort, "xhigh")
        self.assertEqual(len(routed.routing_decisions), 2)
        self.assertEqual(
            RunPlan.from_dict(routed.to_dict()).routing_decisions,
            routed.routing_decisions,
        )


if __name__ == "__main__":
    unittest.main()
