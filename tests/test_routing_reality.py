import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.routing_reality import (  # noqa: E402
    AdapterRouteHealth,
    DirectBaselineReport,
    FailureDomain,
    SelfReportClassification,
    TelemetrySample,
    classify_self_report,
    create_direct_fixture_repository,
    create_fixture_repository,
    required_sample_count,
    summarize_direct_baseline,
    summarize_routes,
)


def sample(route: str, *, cold: bool, total: int, health="ready",
           verification="pass", failure="none") -> TelemetrySample:
    return TelemetrySample(
        route_id=route,
        routing_decision_id=f"routing:{route}",
        routing_decision_digest="sha256:" + "a" * 64,
        provider="codex" if "codex" in route else "claude",
        adapter=route,
        requested_model="fixture-model",
        observed_model="fixture-model",
        requested_effort="medium",
        observed_effort="medium",
        task_kind="implementation",
        risk="low",
        read_only=False,
        cold_start=cold,
        queue_ms=10,
        startup_ms=20,
        provider_start_ms=30,
        first_event_ms=40,
        worker_report_ms=total - 20,
        execution_ms=total - 50,
        collect_ms=5,
        cleanup_ms=15,
        total_ms=total,
        worker_outcome="succeeded",
        verification_outcome=verification,
        structured_result_valid=True,
        rework_count=0,
        scope_violation=False,
        adapter_health=health,
        failure_domain=FailureDomain(failure),
        timestamp="2026-08-14T00:00:00Z",
    )


class RoutingRealityTelemetryTests(unittest.TestCase):
    def test_sample_round_trip_is_bounded_and_contains_no_prompt_or_transcript(self):
        original = sample("direct-codex", cold=True, total=1000)
        value = original.to_dict()
        self.assertNotIn("prompt", value)
        self.assertNotIn("transcript", value)
        self.assertEqual(value["failure_reason"], "")
        self.assertEqual(TelemetrySample.from_dict(value), original)

    def test_summary_separates_cold_and_warm_and_computes_orca_overhead(self):
        samples = (
            sample("direct-codex", cold=True, total=1300),
            sample("direct-codex", cold=False, total=1000),
            sample("direct-codex", cold=False, total=1100),
            sample("orca-codex", cold=True, total=1600),
            sample("orca-codex", cold=False, total=1400),
            sample("orca-codex", cold=False, total=1500),
        )
        report = summarize_routes(samples)
        self.assertEqual(report.routes["direct-codex"].cold_total_ms, 1300)
        self.assertEqual(report.routes["direct-codex"].warm_median_total_ms, 1050)
        self.assertEqual(report.routes["direct-codex"].warm_median_startup_ms, 40)
        self.assertEqual(report.orca_overhead_ms["codex"], 400)
        self.assertEqual(report.routes["direct-codex"].health, AdapterRouteHealth.READY)

    def test_degraded_control_plane_is_not_model_failure_or_unavailable(self):
        report = summarize_routes((
            sample("orca-codex", cold=False, total=1000, health="degraded",
                   failure="adapter"),
        ))
        route = report.routes["orca-codex"]
        self.assertEqual(route.health, AdapterRouteHealth.DEGRADED)
        self.assertEqual(route.failure_domains, (FailureDomain.ADAPTER,))

    def test_adaptive_sampling_adds_only_one_run_above_twenty_percent_variance(self):
        self.assertEqual(required_sample_count((1000, 1100)), 2)
        self.assertEqual(required_sample_count((1000, 1300)), 3)
        self.assertEqual(required_sample_count((1000, 1300, 900)), 3)

    def test_verified_result_preserves_disagreeing_worker_self_report(self):
        value = sample("direct-claude", cold=False, total=1000).to_dict()
        value.update({
            "workload_id": "w2-tiny-write",
            "worker_outcome": "failed",
            "verification_outcome": "pass",
            "worker_report_status": "failed",
            "self_report_disagreement": True,
            "verification_ms": 80,
            "ttur_ms": 1000,
            "effective_time_ms": 1000,
            "usage_status": "unknown",
        })

        restored = TelemetrySample.from_dict(value)

        self.assertEqual(restored.worker_report_status, "failed")
        self.assertTrue(restored.self_report_disagreement)
        self.assertEqual(
            classify_self_report(restored),
            SelfReportClassification.PROVIDER_SELF_REPORT_INCONSISTENCY,
        )
        incomplete = TelemetrySample.from_dict({
            **value, "worker_report_status": "incomplete",
        })
        self.assertEqual(
            classify_self_report(incomplete),
            SelfReportClassification.PROVIDER_SELF_REPORT_INCONSISTENCY,
        )

    def test_direct_baseline_is_grouped_by_workload_without_composite_score(self):
        samples = []
        for route, startup in (("direct-codex", 40), ("direct-claude", 30)):
            for workload, total in (("w1-read", 500), ("w2-tiny-write", 900)):
                cold = sample(route, cold=True, total=total + 100)
                warm_a = sample(route, cold=False, total=total)
                warm_b = sample(route, cold=False, total=total + 20)
                updates = {
                    "workload_id": workload,
                    "verification_ms": 100 if workload == "w2-tiny-write" else 0,
                    "ttur_ms": total,
                    "effective_time_ms": total,
                    "process_spawn_ms": 5,
                    "first_event_ms": startup,
                    "structured_result_ms": total - startup,
                }
                samples.extend(
                    TelemetrySample.from_dict({**item.to_dict(), **updates})
                    for item in (cold, warm_a, warm_b)
                )

        report = summarize_direct_baseline(tuple(samples))

        self.assertIsInstance(report, DirectBaselineReport)
        self.assertEqual(
            report.workloads["direct-codex"]["w2-tiny-write"].warm_median_total_ms,
            910,
        )
        self.assertEqual(report.route_startup_penalty_ms["direct-codex"], 40)
        self.assertEqual(report.route_startup_penalty_ms["direct-claude"], 30)
        self.assertEqual(report.parallel_break_even_ms["direct-codex"], 610)
        self.assertNotIn("score", report.to_dict())


class RoutingRealityFixtureTests(unittest.TestCase):
    def test_fixture_is_a_clean_isolated_git_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = create_fixture_repository(Path(directory) / "rrc")
            self.assertTrue((root / "pyproject.toml").is_file())
            self.assertTrue((root / "src" / "math_utils.py").is_file())
            status = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(status.stdout, "")
            config = json.loads((root / ".graphori-rrc.json").read_text())
            self.assertTrue(config["temporary_fixture"])
            self.assertIn("__pycache__/", (root / ".gitignore").read_text())

    def test_direct_workloads_have_bounded_distinct_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            read = create_direct_fixture_repository(base / "w1", "w1-read")
            tiny = create_direct_fixture_repository(base / "w2", "w2-tiny-write")
            bounded = create_direct_fixture_repository(
                base / "w3", "w3-bounded-implementation",
            )

            self.assertEqual(read.write_scope, ())
            self.assertEqual(tiny.write_scope, ("src/math_utils.py",))
            self.assertEqual(
                bounded.write_scope,
                ("src/inventory.py", "src/reporting.py"),
            )
            self.assertTrue((bounded.root / "tests" / "test_reporting.py").is_file())
            for fixture in (read, tiny, bounded):
                status = subprocess.run(
                    ["git", "-C", str(fixture.root), "status", "--porcelain"],
                    capture_output=True, text=True, check=True,
                )
                self.assertEqual(status.stdout, "")


if __name__ == "__main__":
    unittest.main()
