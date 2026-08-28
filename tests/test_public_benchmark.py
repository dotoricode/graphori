import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = runpy.run_path(ROOT / "benchmarks/three_arm/run.py", run_name="three_arm_test")
ANALYZER = runpy.run_path(ROOT / "benchmarks/three_arm/analyze.py", run_name="three_arm_analyze_test")


class PublicBenchmarkTests(unittest.TestCase):
    def test_all_fixtures_start_failing_and_hide_the_oracle(self):
        for workload in RUNNER["WORKLOADS"]:
            with self.subTest(task=workload.task_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                RUNNER["create_fixture"](root, workload)
                self.assertFalse(RUNNER["test_module"](root, workload.visible_module)["passed"])
                self.assertFalse(RUNNER["hidden_check"](root, workload)["passed"])
                self.assertFalse((root / workload.hidden_path).exists())

    def test_provider_cells_route_to_one_nonpremium_model(self):
        workload = RUNNER["WORKLOADS"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for provider in RUNNER["PROVIDERS"]:
                with self.subTest(provider=provider):
                    _spec, _bundle, worker = RUNNER["compile_bundle"](
                        root, workload, provider, f"test-{provider}",
                    )
                    self.assertEqual(worker.provider, provider)
                    self.assertEqual(worker.adapter, provider)
                    self.assertFalse(worker.approval_required)

    def test_analyzer_rejects_incomplete_matrix(self):
        with self.assertRaisesRegex(ValueError, "matrix mismatch"):
            ANALYZER["summarize"]([], 3)

    def test_runner_accepts_exact_repetition_replay_option(self):
        args = RUNNER["build_parser"]().parse_args(["--repetition", "3"])
        self.assertEqual(args.repetition, 3)

    def test_raw_schema_accepts_v1_and_v2(self):
        schema = json.loads((ROOT / "benchmarks/raw-result.schema.json").read_text())
        self.assertEqual(schema["properties"]["schema_version"]["enum"], [1, 2])

    def test_published_readmes_contain_every_calculated_metric(self):
        result_path = ROOT / "benchmarks/three_arm/results.json"
        if not result_path.exists():
            self.skipTest("generated result is not present")
        result = json.loads(result_path.read_text())
        english = (ROOT / "README.md").read_text()
        korean = (ROOT / "README.ko.md").read_text()
        for provider in ("codex", "claude"):
            for arm in ("direct", "v1-style", "graphori-v2"):
                cell = result["providers"][provider][arm]
                for key in ("total_input_tokens", "cached_input_tokens",
                            "fresh_input_tokens", "output_tokens"):
                    value = f"{cell[key]:,}"
                    self.assertIn(value, english)
                    self.assertIn(value, korean)
                ttur = f"{cell['median_ttur_seconds']:.3f}"
                self.assertIn(ttur, english)
                self.assertIn(ttur, korean)


if __name__ == "__main__":
    unittest.main()
