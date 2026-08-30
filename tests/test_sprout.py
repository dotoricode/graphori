import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    GrowthCandidate,
    NodeSpec,
    ProofCarryingArtifact,
    ProofFrontier,
    ProofObligation,
    ProofResult,
    RunPlan,
    TransitionAuthority,
)


def node(node_id, *, closes=()):
    return NodeSpec(
        node_id, "implementation", node_id, node_id, "worker",
        closes_proofs=closes,
    )


class ProofCarryingArtifactTests(unittest.TestCase):
    def test_open_failed_and_unknown_obligations_are_explicit(self):
        artifact = ProofCarryingArtifact(
            "artifact:pilot", "sha256:" + "a" * 64,
            claims=("pilot is valid",), journal_ref="journal:pilot",
            obligations=(
                ProofObligation("schema", "schema-check"),
                ProofObligation("tests", "unit-test"),
                ProofObligation("judgment", "human"),
            ),
            results=(
                ProofResult("schema", "passed", ("evidence:schema",)),
                ProofResult("tests", "failed", ("evidence:tests",)),
                ProofResult("judgment", "unknown"),
            ),
        )
        self.assertEqual(artifact.failed_obligations, ("tests",))
        self.assertEqual(artifact.unknown_obligations, ("judgment",))
        self.assertEqual(artifact.open_obligations, ())
        self.assertFalse(artifact.qualified)

    def test_duplicate_or_undeclared_results_are_rejected(self):
        obligation = ProofObligation("tests", "unit-test")
        with self.assertRaisesRegex(ValueError, "duplicate proof result"):
            ProofCarryingArtifact(
                "artifact:a", "sha256:" + "a" * 64,
                journal_ref="journal:a",
                obligations=(obligation,),
                results=(ProofResult("tests", "passed", ("e:a",)),
                         ProofResult("tests", "passed", ("e:b",))),
            )
        with self.assertRaisesRegex(ValueError, "undeclared proof"):
            ProofCarryingArtifact(
                "artifact:a", "sha256:" + "a" * 64,
                journal_ref="journal:a",
                obligations=(obligation,),
                results=(ProofResult("scope", "passed", ("e:a",)),),
            )

    def test_sprout_fields_round_trip_through_run_plan(self):
        original = node("verify", closes=("pilot-qualified",))
        restored = NodeSpec.from_dict(original.to_dict())
        self.assertEqual(restored, original)

    def test_candidate_contract_must_match_runtime_node(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            GrowthCandidate(node("verify", closes=("actual",)), ("claimed",))


class ProofFrontierTests(unittest.TestCase):
    def setUp(self):
        self.frontier = ProofFrontier(policy_version="sprout-1")

    def artifact(self, *results, artifact_id="artifact:pilot"):
        obligations = tuple(
            ProofObligation(name, f"verify-{name}") for name, _state in results
        )
        return ProofCarryingArtifact(
            artifact_id, "sha256:" + "b" * 64,
            claims=("result is qualified",), journal_ref="journal:pilot",
            obligations=obligations,
            results=tuple(
                ProofResult(name, state, (f"evidence:{name}",) if state != "unknown" else ())
                for name, state in results
            ),
        )

    def test_expand_requires_a_fully_qualified_pilot(self):
        failed = self.artifact(("pilot", "failed"))
        denied = self.frontier.authorize(
            TransitionAuthority.EXPAND,
            (failed,),
            scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({failed.digest()}),
        )
        self.assertFalse(denied.granted)
        self.assertEqual(denied.reason, "failed_proof")

        passed = self.artifact(("pilot", "passed"))
        granted = self.frontier.authorize(
            TransitionAuthority.EXPAND,
            (passed,),
            scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({passed.digest()}),
        )
        self.assertTrue(granted.granted)
        self.assertEqual(granted.proof_refs, ("evidence:pilot",))

    def test_fan_in_rejects_one_unqualified_branch(self):
        first = self.artifact(("a", "passed"), artifact_id="artifact:a")
        second = self.artifact(("b", "unknown"), artifact_id="artifact:b")
        decision = self.frontier.authorize(
            TransitionAuthority.FAN_IN,
            (first, second),
            scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({first.digest(), second.digest()}),
        )
        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason, "unknown_proof")

    def test_planning_evaluator_never_grants_irreversible_commit(self):
        artifact = self.artifact(("synthesis", "passed"))
        denied = self.frontier.authorize(
            TransitionAuthority.COMMIT, (artifact,), irreversible=True,
            scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({artifact.digest()}),
        )
        self.assertFalse(denied.granted)
        self.assertEqual(denied.reason, "runtime_human_gate_required")
        still_denied = self.frontier.authorize(
            "commit", (artifact,), irreversible=True,
            human_proof="evidence:human:approved",
            scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({artifact.digest()}),
        )
        self.assertFalse(still_denied.granted)

    def test_route_activates_a_low_latency_candidate_cover(self):
        artifact = ProofCarryingArtifact(
            "artifact:work", "sha256:" + "c" * 64,
            journal_ref="journal:work",
            obligations=(
                ProofObligation("schema", "schema-check"),
                ProofObligation("tests", "unit-test"),
                ProofObligation("scope", "scope-check"),
            ),
        )
        decision = self.frontier.route(
            artifact,
            (
                GrowthCandidate(node("schema", closes=("schema",)), ("schema",)),
                GrowthCandidate(node("tests", closes=("tests",)), ("tests",)),
                GrowthCandidate(node("combined", closes=("schema", "tests")),
                                ("schema", "tests")),
                GrowthCandidate(node("scope", closes=("scope",)), ("scope",)),
            ),
            branch_budget=2,
        )
        self.assertEqual(decision.action, "spawn")
        self.assertEqual(decision.target_node_ids, ("combined", "scope"))
        self.assertEqual(decision.target_obligations, ("schema", "scope", "tests"))

    def test_route_escalates_unknown_and_retries_failed_proof(self):
        unknown = self.frontier.route(self.artifact(("meaning", "unknown")), ())
        self.assertEqual(unknown.action, "escalate")
        failed = self.frontier.route(
            self.artifact(("tests", "failed")),
            (GrowthCandidate(node("repair", closes=("tests",)), ("tests",)),),
        )
        self.assertEqual(failed.action, "retry")
        self.assertEqual(failed.target_node_ids, ("repair",))

    def test_route_fails_closed_before_combinatorial_search_can_explode(self):
        artifact = ProofCarryingArtifact(
            "artifact:bounded", "sha256:" + "d" * 64,
            journal_ref="journal:bounded",
            obligations=tuple(ProofObligation(f"proof-{index}", "verify")
                              for index in range(33)),
        )
        candidates = tuple(
            GrowthCandidate(node(f"candidate-{index}", closes=(f"proof-{index}",)),
                            (f"proof-{index}",))
            for index in range(33)
        )
        decision = self.frontier.route(artifact, candidates, branch_budget=4)
        self.assertEqual(decision.action, "escalate")
        self.assertEqual(decision.reason, "search_budget_exceeded")

    def test_route_bounds_candidate_preprocessing(self):
        artifact = ProofCarryingArtifact(
            "artifact:input-bound", "sha256:" + "1" * 64,
            journal_ref="journal:input-bound",
            obligations=(ProofObligation("proof", "verify"),),
        )
        candidates = tuple(
            GrowthCandidate(
                node(f"candidate-{index}", closes=("proof",)), ("proof",),
            )
            for index in range(257)
        )
        decision = self.frontier.route(artifact, candidates)
        self.assertEqual(decision.action, "escalate")
        self.assertEqual(decision.reason, "candidate_input_exceeded")

    def test_planning_authority_requires_a_caller_trusted_digest(self):
        artifact = self.artifact(("pilot", "passed"))
        decision = self.frontier.authorize(
            TransitionAuthority.EXPAND, (artifact,), scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset(),
        )
        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason, "artifact_not_trusted")

        claimless = ProofCarryingArtifact(
            "artifact:claimless", "sha256:" + "3" * 64,
            journal_ref="journal:claimless",
            obligations=(ProofObligation("pilot", "verify"),),
            results=(ProofResult("pilot", "passed", ("evidence:pilot",)),),
        )
        decision = self.frontier.authorize(
            TransitionAuthority.EXPAND, (claimless,), scope_digest="sha256:plan",
            trusted_artifact_digests=frozenset({claimless.digest()}),
        )
        self.assertFalse(decision.granted)
        self.assertEqual(decision.reason, "missing_claim")

    def test_expand_plan_is_immutable_and_replayable(self):
        pilot = node("pilot")
        base = RunPlan(
            "run-sprout", 1, "committed", proof_policy="sprout-1", nodes=(pilot,),
        )
        artifact = self.artifact(("pilot", "passed"))
        branches = (node("branch-a", closes=("a",)),
                    node("branch-b", closes=("b",)))
        persisted = frozenset({artifact.digest()})
        first = self.frontier.expand_plan(
            base, branches, (artifact,), trusted_artifact_digests=persisted,
        )
        second = self.frontier.expand_plan(
            base, branches, (artifact,), trusted_artifact_digests=persisted,
        )
        self.assertEqual(base.plan_version, 1)
        self.assertEqual(first.plan_version, 2)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(tuple(item.node_id for item in first.nodes),
                         ("branch-a", "branch-b", "pilot"))

    def test_expansion_rejects_unpersisted_or_proofless_input(self):
        base = RunPlan(
            "run-sprout", 1, "committed", proof_policy="sprout-1",
            nodes=(node("pilot"),),
        )
        unpersisted = ProofCarryingArtifact(
            "artifact:pilot", "sha256:" + "e" * 64,
            obligations=(ProofObligation("pilot", "verify"),),
            results=(ProofResult("pilot", "passed", ("evidence:pilot",)),),
        )
        with self.assertRaisesRegex(ValueError, "granted EXPAND"):
            self.frontier.expand_plan(
                base, (node("branch", closes=("branch",)),), (unpersisted,),
                trusted_artifact_digests=frozenset({unpersisted.digest()}),
            )
        with self.assertRaisesRegex(ValueError, "close a proof"):
            artifact = self.artifact(("pilot", "passed"))
            self.frontier.expand_plan(
                base, (node("branch"),), (artifact,),
                trusted_artifact_digests=frozenset({artifact.digest()}),
            )

    def test_cover_optimizes_parallel_latency_before_node_count(self):
        artifact = ProofCarryingArtifact(
            "artifact:latency", "sha256:" + "f" * 64,
            journal_ref="journal:latency",
            obligations=(ProofObligation("a", "verify"),
                         ProofObligation("b", "verify")),
        )
        slow = NodeSpec("slow", "verification", "slow", "slow", "verifier",
                        estimated_execution_ms=1_000, closes_proofs=("a", "b"))
        fast_a = NodeSpec("fast-a", "verification", "fast-a", "fast-a", "verifier",
                          estimated_execution_ms=10, closes_proofs=("a",))
        fast_b = NodeSpec("fast-b", "verification", "fast-b", "fast-b", "verifier",
                          estimated_execution_ms=10, closes_proofs=("b",))
        decision = self.frontier.route(
            artifact,
            (GrowthCandidate(slow, ("a", "b")),
             GrowthCandidate(fast_a, ("a",)), GrowthCandidate(fast_b, ("b",))),
            branch_budget=2,
        )
        self.assertEqual(decision.target_node_ids, ("fast-a", "fast-b"))

    def test_pilot_runs_only_after_declared_break_even(self):
        artifact = ProofCarryingArtifact(
            "artifact:repeat", "sha256:" + "2" * 64,
            journal_ref="journal:repeat",
            obligations=(ProofObligation("a", "verify"),
                         ProofObligation("b", "verify")),
        )
        static = (
            NodeSpec("static-a", "verification", "a", "a", "verifier",
                     estimated_execution_ms=100, closes_proofs=("a",)),
            NodeSpec("static-b", "verification", "b", "b", "verifier",
                     estimated_execution_ms=100, closes_proofs=("b",)),
        )
        compound = NodeSpec(
            "compound", "verification", "compound", "compound", "verifier",
            estimated_execution_ms=110, closes_proofs=("a", "b"),
        )
        candidates = (GrowthCandidate(compound, ("a", "b")),)

        small = self.frontier.route_if_profitable(
            artifact, candidates, static, target_count=1, max_wip=1,
            min_gain_ms=0, min_gain_ratio=0,
        )
        repeated = self.frontier.route_if_profitable(
            artifact, candidates, static, target_count=4, max_wip=1,
            min_gain_ms=0, min_gain_ratio=0,
        )

        self.assertEqual(small.action, "use_static")
        self.assertEqual(small.reason, "pilot_not_profitable")
        self.assertEqual(repeated.action, "spawn")

    def test_performance_gate_rejects_scope_conflict(self):
        artifact = ProofCarryingArtifact(
            "artifact:conflict", "sha256:" + "4" * 64,
            obligations=(ProofObligation("a", "verify"),
                         ProofObligation("b", "verify")),
        )
        static = (NodeSpec(
            "static", "verification", "static", "static", "verifier",
            estimated_execution_ms=180, closes_proofs=("a", "b"),
        ),)
        candidates = tuple(
            GrowthCandidate(NodeSpec(
                f"sparse-{proof}", "verification", proof, proof, "verifier",
                estimated_execution_ms=60, write_scope=("shared",),
                closes_proofs=(proof,),
            ), (proof,))
            for proof in ("a", "b")
        )
        decision = self.frontier.route_if_profitable(
            artifact, candidates, static, target_count=1, max_wip=2,
            min_gain_ms=0, min_gain_ratio=0,
        )
        self.assertEqual(decision.action, "use_static")
        self.assertEqual(decision.reason, "pilot_schedule_uncertain")

    def test_performance_gate_rejects_repeated_writer_serialization(self):
        artifact = ProofCarryingArtifact(
            "artifact:repeat-writer", "sha256:" + "5" * 64,
            obligations=(ProofObligation("proof", "verify"),),
        )
        static = (NodeSpec(
            "static", "verification", "static", "static", "verifier",
            estimated_execution_ms=100, closes_proofs=("proof",),
        ),)
        sparse = NodeSpec(
            "sparse", "verification", "sparse", "sparse", "verifier",
            estimated_execution_ms=60, write_scope=("shared",),
            closes_proofs=("proof",),
        )
        decision = self.frontier.route_if_profitable(
            artifact, (GrowthCandidate(sparse, ("proof",)),), static,
            target_count=4, max_wip=2, min_gain_ms=0, min_gain_ratio=0,
        )
        self.assertEqual(decision.action, "use_static")
        self.assertEqual(decision.reason, "pilot_schedule_uncertain")


if __name__ == "__main__":
    unittest.main()
