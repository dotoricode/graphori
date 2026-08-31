from copy import deepcopy
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).parents[1]
RUNNER = runpy.run_path(ROOT / "benchmarks/sprout/run.py", run_name="sprout_runner")
ANALYZER = runpy.run_path(ROOT / "benchmarks/sprout/analyze.py", run_name="sprout_analyzer")


class SproutBenchmarkTests(unittest.TestCase):
    def test_every_arm_covers_the_same_declared_target_proofs(self):
        for work in RUNNER["MATRIX"]:
            for arm in RUNNER["ARMS"]:
                with self.subTest(workload=work.workload_id, arm=arm):
                    row = RUNNER["run_cell"](work, arm, 1, 8)
                    self.assertEqual(
                        row["declared_proofs_closed"], row["declared_proofs_total"]
                    )
                    self.assertEqual(row["invalid_fan_in"], 0)

    def test_fixture_jitter_is_paired_across_arms_and_branch_counts(self):
        work = RUNNER["MATRIX"][0]
        digests = {
            RUNNER["run_cell"](work, arm, 2, branches)["fixture_digest"]
            for arm in RUNNER["ARMS"] for branches in (1, 16)
        }
        self.assertEqual(len(digests), 1)

    def test_workloads_have_distinct_structures(self):
        structures = {
            (work.obligations,
             tuple((item.closes, item.cost_ms, item.executor) for item in work.candidates))
            for work in RUNNER["MATRIX"]
        }
        self.assertEqual(len(structures), len(RUNNER["MATRIX"]))

    def test_oracle_exposes_the_full_sprout_pilot_overhead(self):
        work = RUNNER["MATRIX"][1]
        sprout = RUNNER["run_cell"](work, "sprout-unconditional", 1, 8)
        oracle = RUNNER["run_cell"](work, "oracle-static", 1, 8)
        self.assertEqual(sprout["selected_nodes"], oracle["selected_nodes"])
        self.assertEqual(
            sprout["modeled_latency_ms"] - oracle["modeled_latency_ms"],
            sprout["pilot_modeled_latency_ms"],
        )
        self.assertEqual(
            sprout["activated_nodes"] - oracle["activated_nodes"],
            sprout["pilot_activated_nodes"],
        )
        self.assertEqual(
            sprout["ai_nodes"] - oracle["ai_nodes"], sprout["pilot_ai_nodes"]
        )
        self.assertEqual(
            sprout["process_nodes"] - oracle["process_nodes"],
            sprout["pilot_process_nodes"],
        )

    def test_adaptive_sprout_never_exceeds_v2_modeled_latency(self):
        for work in RUNNER["MATRIX"]:
            for branches in RUNNER["BRANCH_COUNTS"]:
                sprout = RUNNER["run_cell"](
                    work, "graphori-sprout", 1, branches,
                )
                v2 = RUNNER["run_cell"](work, "graphori-v2", 1, branches)
                self.assertLessEqual(
                    sprout["modeled_latency_ms"], v2["modeled_latency_ms"],
                )

    def test_actual_route_is_v2_for_small_targets_and_shadow_is_deterministic(self):
        work = RUNNER["MATRIX"][0]
        for branches in (1, 2):
            row = RUNNER["run_cell"](work, "graphori-sprout", 1, branches)
            self.assertEqual(row["actual_route"], "v2")
            self.assertFalse(row["pilot_used"])
            self.assertTrue(row["shadow_planning"])
            self.assertEqual(row["proof_coverage_delta"], 0)
        first = RUNNER["run_cell"](work, "graphori-sprout", 2, 8)
        second = RUNNER["run_cell"](work, "graphori-sprout", 2, 8)
        shadow_keys = (
            "shadow_action", "shadow_selected_nodes", "activation_eligible",
            "activation_reason", "estimated_v2_latency_ms",
            "estimated_shadow_latency_ms", "estimated_gain_ms",
            "proof_coverage_delta", "incorrect_expansion", "missed_expansion",
        )
        self.assertEqual(
            tuple(first[key] for key in shadow_keys),
            tuple(second[key] for key in shadow_keys),
        )

    def test_conditional_activation_requires_four_independent_covered_targets(self):
        for work in RUNNER["MATRIX"]:
            for branches in RUNNER["BRANCH_COUNTS"]:
                row = RUNNER["run_cell"](
                    work, "graphori-sprout", 1, branches,
                )
                self.assertGreaterEqual(row["proof_coverage_delta"], 0)
                self.assertEqual(row["incorrect_expansion"], 0)
                if row["actual_route"] == "sprout":
                    self.assertGreaterEqual(branches, 4)
                    self.assertTrue(row["activation_eligible"])
                    self.assertGreater(row["estimated_gain_ms"], 0)

    def test_analysis_rejects_unpaired_arm_jitter(self):
        rows = [
            RUNNER["run_cell"](work, arm, 1, 1)
            for work in RUNNER["MATRIX"] for arm in RUNNER["ARMS"]
        ]
        mismatched = deepcopy(rows)
        mismatched[0]["fixture_digest"] = "sha256:unpaired"
        with self.assertRaisesRegex(ValueError, "different latency fixtures"):
            ANALYZER["summarize"](mismatched, 1, (1,))

    def test_generated_sensitivity_matrix_is_complete_and_reproducible(self):
        branch_counts = (1, 4, 16)
        rows = [
            RUNNER["run_cell"](work, arm, repetition, branches)
            for repetition in range(1, 3)
            for work in RUNNER["MATRIX"]
            for branches in branch_counts
            for arm in RUNNER["ARMS"]
        ]
        first = ANALYZER["summarize"](rows, 2, branch_counts)
        second = ANALYZER["summarize"](rows, 2, branch_counts)
        self.assertEqual(first, second)
        self.assertEqual(first["matrix"]["runs"], 120)
        self.assertEqual(set(first["sensitivity"]), {"1", "4", "16"})


if __name__ == "__main__":
    unittest.main()
