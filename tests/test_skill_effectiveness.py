import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.skill_effectiveness import (  # noqa: E402
    SkillBenchmarkSample,
    SkillValueClassification,
    classify_skill_value,
    diff_metrics,
    needs_additional_pair,
    paired_orders,
)


def sample(arm: str, ttur: int, *, added: int = 10, verification: str = "pass",
           scope: bool = False, rework: int = 0, structured: bool = True
           ) -> SkillBenchmarkSample:
    return SkillBenchmarkSample(
        provider="codex", model="gpt-5.6-luna", effort="medium",
        workload="w3-bounded-implementation", arm=arm, pair_id="pair-1",
        repetition=1, order_index=0,
        skill_id="ponytail" if arm == "ponytail-full" else "",
        skill_digest="sha256:abc" if arm == "ponytail-full" else "",
        skill_source_revision="local-sha256:abc" if arm == "ponytail-full" else "",
        skill_args=("full",) if arm == "ponytail-full" else (),
        startup_ms=1, first_event_ms=2, execution_ms=ttur - 5,
        structured_result_ms=2, verification_ms=2, ttur_ms=ttur,
        total_ms=ttur, effective_time_ms=ttur,
        worker_report_status="succeeded", structured_result_valid=structured,
        verification=verification, scope_violation=scope, rework_count=rework,
        files_changed=1, lines_added=added, lines_deleted=1, new_files=0,
        new_dependencies=0, skill_snapshot_verified=bool(arm == "ponytail-full"),
        binding_rendered=bool(arm == "ponytail-full"),
    )


class SkillEffectivenessPolicyTests(unittest.TestCase):
    def test_paired_orders_are_ab_then_ba(self):
        self.assertEqual(
            paired_orders(2),
            (
                ("no-skill", "ponytail-full"),
                ("ponytail-full", "no-skill"),
            ),
        )

    def test_only_ambiguous_equal_quality_result_requests_one_more_pair(self):
        ambiguous = [
            sample("no-skill", 100), sample("ponytail-full", 105),
            sample("no-skill", 102), sample("ponytail-full", 100),
        ]
        clear = [
            sample("no-skill", 100), sample("ponytail-full", 135),
            sample("no-skill", 102), sample("ponytail-full", 130),
        ]
        self.assertTrue(needs_additional_pair(ambiguous))
        self.assertFalse(needs_additional_pair(clear))

        unstable = [
            replace(sample("no-skill", 100), pair_id="pair-1"),
            replace(sample("ponytail-full", 130), pair_id="pair-1"),
            replace(sample("no-skill", 140), pair_id="pair-2"),
            replace(sample("ponytail-full", 100), pair_id="pair-2"),
        ]
        self.assertTrue(needs_additional_pair(unstable))

    def test_sample_result_schema_round_trips(self):
        original = sample("ponytail-full", 90)
        self.assertEqual(SkillBenchmarkSample.from_dict(original.to_dict()), original)

    def test_classification_is_correctness_first_then_ttur_and_loc(self):
        auto = [
            sample("no-skill", 100, added=20), sample("ponytail-full", 80, added=12),
            sample("no-skill", 110, added=20), sample("ponytail-full", 90, added=12),
        ]
        manual = [
            sample("no-skill", 100, added=20), sample("ponytail-full", 108, added=10),
            sample("no-skill", 100, added=20), sample("ponytail-full", 106, added=10),
        ]
        neutral = [
            sample("no-skill", 100, added=20), sample("ponytail-full", 103, added=19),
            sample("no-skill", 100, added=20), sample("ponytail-full", 102, added=19),
        ]
        harmful = [
            sample("no-skill", 100), sample("ponytail-full", 80, verification="revise"),
            sample("no-skill", 100), sample("ponytail-full", 85),
        ]
        self.assertEqual(classify_skill_value(auto), SkillValueClassification.AUTO_CANDIDATE)
        self.assertEqual(classify_skill_value(manual), SkillValueClassification.MANUAL_ONLY)
        self.assertEqual(classify_skill_value(neutral), SkillValueClassification.NO_BENEFIT)
        self.assertEqual(classify_skill_value(harmful), SkillValueClassification.HARMFUL)
        self.assertEqual(
            classify_skill_value(auto[:2]), SkillValueClassification.INSUFFICIENT_DATA,
        )


class DiffMetricsTests(unittest.TestCase):
    def test_git_diff_metrics_are_deterministic_and_dependency_free(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email",
                            "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"],
                           check=True)
            (root / "a.py").write_text("one\ntwo\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
            (root / "a.py").write_text("one\nthree\nfour\n", encoding="utf-8")
            (root / "new.py").write_text("new\n", encoding="utf-8")

            metrics = diff_metrics(root)

            self.assertEqual(metrics.files_changed, 2)
            self.assertEqual(metrics.lines_added, 3)
            self.assertEqual(metrics.lines_deleted, 1)
            self.assertEqual(metrics.new_files, 1)
            self.assertEqual(metrics.new_dependencies, 0)


if __name__ == "__main__":
    unittest.main()
