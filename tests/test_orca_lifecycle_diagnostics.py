import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.orca_lifecycle import (  # noqa: E402
    InstructionDeliveryEvidence,
    LifecycleFailureStage,
    OrcaLaunchStrategy,
    OrcaLifecycleTimeline,
    RouteCircuitBreaker,
    RouteHealthKey,
    RouteHealthStatus,
)


def key(*, version="1.4.182", runtime="runtime-a", guide="sha256:guide",
        provider="codex", agent_version="0.147.0",
        strategy=OrcaLaunchStrategy.ORCA_COMPOSED):
    return RouteHealthKey(
        version, runtime, guide, provider, agent_version, strategy,
    )


class InstructionDeliveryEvidenceTests(unittest.TestCase):
    def test_ready_agent_without_sent_instruction_is_not_delivered(self):
        evidence = InstructionDeliveryEvidence(
            provider="codex", arm="ready-terminal", nonce="nonce-ready",
            process_started=True, agent_ready=True, instruction_sent=False,
        )
        self.assertEqual(
            evidence.stage, LifecycleFailureStage.INSTRUCTION_NOT_DELIVERED,
        )

    def test_accepted_instruction_without_task_effect_is_delivery_only(self):
        evidence = InstructionDeliveryEvidence(
            provider="claude", arm="orchestration", nonce="nonce-accepted",
            process_started=True, agent_ready=True, instruction_sent=True,
            task_effect_observed=False,
        )
        self.assertEqual(evidence.stage, LifecycleFailureStage.INSTRUCTION_DELIVERED)

    def test_stage_distinguishes_instruction_effect_from_worker_done(self):
        evidence = InstructionDeliveryEvidence(
            provider="codex", arm="orchestration", nonce="nonce-a",
            process_started=True, agent_ready=True, instruction_sent=True,
            task_effect_observed=True, lifecycle_contract_observed=True,
            completion_attempt_observed=False, worker_done_observed=False,
            delivery_observed=False, graphori_correlated=False,
        )
        self.assertEqual(evidence.stage, LifecycleFailureStage.WORKER_DONE_NOT_EMITTED)

    def test_complete_requires_delivery_correlation_journal_ack_and_release(self):
        timeline = OrcaLifecycleTimeline(
            run_create_at="2026-08-14T00:00:00Z",
            task_create_at="2026-08-14T00:00:01Z",
            worker_start_requested_at="2026-08-14T00:00:02Z",
            worker_start_returned_at="2026-08-14T00:00:03Z",
            terminal_handle_observed_at="2026-08-14T00:00:03Z",
            agent_process_observed_at="2026-08-14T00:00:03Z",
            first_terminal_activity_at="2026-08-14T00:00:04Z",
            sentinel_created_at="2026-08-14T00:00:05Z",
            agent_exit_observed_at=None,
            worker_done_observed_at="2026-08-14T00:00:06Z",
            delivery_observed_at="2026-08-14T00:00:06Z",
            journaled_at="2026-08-14T00:00:07Z",
            acked_at="2026-08-14T00:00:08Z",
            released_at="2026-08-14T00:00:09Z",
        )
        evidence = InstructionDeliveryEvidence(
            provider="claude", arm="ready-terminal", nonce="nonce-b",
            process_started=True, agent_ready=True, instruction_sent=True,
            task_effect_observed=True, lifecycle_contract_observed=True,
            completion_attempt_observed=True, worker_done_observed=True,
            delivery_observed=True, graphori_correlated=True,
            timeline=timeline,
        )
        self.assertEqual(evidence.stage, LifecycleFailureStage.COMPLETE)
        self.assertEqual(
            InstructionDeliveryEvidence.from_dict(evidence.to_dict()), evidence,
        )


class RouteCircuitBreakerTests(unittest.TestCase):
    def test_composed_block_does_not_block_ready_terminal_strategy(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = RouteCircuitBreaker(Path(directory) / "health.json")
            composed = key(strategy=OrcaLaunchStrategy.ORCA_COMPOSED)
            ready = key(strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL)
            registry.record(
                composed, RouteHealthStatus.BLOCKED, "fresh worker readiness race",
            )

            self.assertEqual(registry.status(composed), RouteHealthStatus.BLOCKED)
            self.assertEqual(registry.status(ready), RouteHealthStatus.RECHECK)
            self.assertTrue(registry.allows_pre_dispatch(ready))

    def test_schema_v1_route_is_migrated_as_composed_without_rewriting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            legacy_key = {
                "orca_version": "1.4.182",
                "runtime_id": "runtime-a",
                "guide_digest": "sha256:guide",
                "agent_provider": "codex",
                "agent_version": "0.147.0",
            }
            path.write_text(json.dumps({
                "schema_version": 1,
                "records": [{
                    "key": legacy_key,
                    "status": "blocked",
                    "reason": "RRC-02 composed failure",
                    "observed_at": "2026-08-14T00:00:00Z",
                }],
            }), encoding="utf-8")

            registry = RouteCircuitBreaker(path)

            self.assertEqual(
                registry.status(key(strategy=OrcaLaunchStrategy.ORCA_COMPOSED)),
                RouteHealthStatus.BLOCKED,
            )
            self.assertEqual(
                registry.status(key(strategy=OrcaLaunchStrategy.ORCA_READY_TERMINAL)),
                RouteHealthStatus.RECHECK,
            )
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)

    def test_blocked_route_is_excluded_before_dispatch_and_direct_fallback_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = RouteCircuitBreaker(Path(directory) / "health.json")
            orca = key()
            direct = key(version="direct", runtime="local", guide="none")
            registry.record(orca, RouteHealthStatus.BLOCKED, "worker_done missing")
            registry.record(direct, RouteHealthStatus.READY, "direct smoke passed")

            self.assertFalse(registry.allows_pre_dispatch(orca))
            self.assertEqual(registry.select_pre_dispatch((orca, direct)), direct)

            restored = RouteCircuitBreaker(Path(directory) / "health.json")
            self.assertEqual(restored.status(orca), RouteHealthStatus.BLOCKED)

    def test_version_runtime_guide_or_agent_change_resets_to_recheck(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = RouteCircuitBreaker(Path(directory) / "health.json")
            registry.record(key(), RouteHealthStatus.BLOCKED, "fixture")
            for changed in (
                key(version="1.4.183"), key(runtime="runtime-b"),
                key(guide="sha256:new"), key(agent_version="0.148.0"),
            ):
                self.assertEqual(registry.status(changed), RouteHealthStatus.RECHECK)
                self.assertTrue(registry.allows_pre_dispatch(changed))

    def test_post_dispatch_outcome_unknown_never_automatically_falls_back(self):
        self.assertFalse(RouteCircuitBreaker.allows_automatic_fallback(
            dispatch_started=True, outcome="outcome_unknown",
        ))
        self.assertTrue(RouteCircuitBreaker.allows_automatic_fallback(
            dispatch_started=False, outcome="adapter_unavailable",
        ))

    def test_explicit_recheck_removes_only_the_exact_health_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            registry = RouteCircuitBreaker(path)
            codex = key(provider="codex")
            claude = key(provider="claude", agent_version="2.1.220")
            registry.record(codex, RouteHealthStatus.BLOCKED, "codex")
            registry.record(claude, RouteHealthStatus.BLOCKED, "claude")
            registry.request_recheck(codex)
            self.assertEqual(registry.status(codex), RouteHealthStatus.RECHECK)
            self.assertEqual(registry.status(claude), RouteHealthStatus.BLOCKED)
            self.assertEqual(len(json.loads(path.read_text())["records"]), 1)


if __name__ == "__main__":
    unittest.main()
