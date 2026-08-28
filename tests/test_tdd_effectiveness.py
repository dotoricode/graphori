import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.tdd_effectiveness import (
    NO_SKILL,
    TDD,
    TddBenchmarkSample,
    TddValueClassification,
    classify_tdd_value,
    create_tdd_fixture_repository,
    inspect_test_quality,
    mutation_detected,
    paired_tdd_orders,
    verify_tdd_fixture,
)


def sample(arm: str, effective: int, *, escaped: bool = False,
           verification: str = "pass", mutation: bool = True,
           scope: bool = False) -> TddBenchmarkSample:
    return TddBenchmarkSample(
        provider="codex", model="gpt-5.6-luna", effort="medium",
        workload="w4-regression-prone", arm=arm, pair_id="pair-1",
        repetition=1, order_index=0, ttur_ms=effective,
        effective_time_ms=effective, worker_report_status="succeeded",
        structured_result_valid=True, verification=verification,
        scope_violation=scope, escaped_defect=escaped,
        rework_count=int(escaped), regression_test_exists=True,
        mutation_detected=mutation, public_seam_test=True,
    )


class TddPolicyTests(unittest.TestCase):
    def test_orders_are_ab_then_ba(self):
        self.assertEqual(
            paired_tdd_orders(2),
            ((NO_SKILL, TDD), (TDD, NO_SKILL)),
        )

    def test_sample_schema_round_trips(self):
        original = sample(TDD, 120)
        self.assertEqual(TddBenchmarkSample.from_dict(original.to_dict()), original)

    def test_regression_reduction_with_bounded_penalty_is_conditional(self):
        values = [
            sample(NO_SKILL, 100, escaped=True, mutation=False),
            sample(TDD, 112),
            sample(NO_SKILL, 105, escaped=True, mutation=False),
            sample(TDD, 115),
        ]
        self.assertEqual(classify_tdd_value(values), TddValueClassification.CONDITIONAL)

    def test_no_quality_gain_is_no_benefit_and_regression_is_harmful(self):
        neutral = [
            sample(NO_SKILL, 100), sample(TDD, 125),
            sample(NO_SKILL, 102), sample(TDD, 128),
        ]
        harmful = [
            sample(NO_SKILL, 100), sample(TDD, 90, verification="revise"),
            sample(NO_SKILL, 102), sample(TDD, 95),
        ]
        self.assertEqual(classify_tdd_value(neutral), TddValueClassification.NO_BENEFIT)
        self.assertEqual(classify_tdd_value(harmful), TddValueClassification.HARMFUL)


class TddFixtureTests(unittest.TestCase):
    def test_w4_has_preapproved_public_seams_and_independent_edge_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = create_tdd_fixture_repository(Path(temp) / "fixture", "w4-regression-prone")
            self.assertIn("approved_test_seams", fixture.preconditions)
            self.assertIn("parse_retry_after", " ".join(fixture.acceptance_criteria))
            self.assertIn("tests/test_retry_after.py", fixture.write_scope)
            self.assertEqual(verify_tdd_fixture(fixture), ("revise", 1))

    def test_test_quality_and_hand_authored_mutation_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = create_tdd_fixture_repository(Path(temp) / "fixture", "w2-tiny-write")
            (fixture.root / "src" / "math_utils.py").write_text(
                "def add(a, b):\n    return a + b\n", encoding="utf-8",
            )
            quality = inspect_test_quality(fixture)
            self.assertTrue(quality.public_seam_test)
            self.assertEqual(quality.private_method_test_count, 0)
            self.assertEqual(quality.implementation_mock_count, 0)
            self.assertTrue(mutation_detected(fixture))


if __name__ == "__main__":
    unittest.main()
