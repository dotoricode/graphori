import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core.cli import main  # noqa: E402

PY = sys.executable


def _run_cli(args):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class CliRunStatusReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_zero_exit_records_execution_success_but_waits_for_verification(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-ok", "run",
            "--", PY, "-c", "import sys; sys.exit(0)",
        ])
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertIsNone(summary["terminal_status"])
        self.assertEqual(summary["execution_outcome"], "succeeded")
        self.assertEqual(summary["exit_code"], 0)

        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-ok", "status", "--json",
        ])
        self.assertEqual(code, 0)
        status = json.loads(out)
        self.assertIsNone(status["terminal_status"])
        self.assertEqual(status["node_states"]["worker"], "awaiting_verification")
        self.assertEqual(status["event_count"], 8)

        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-ok", "replay", "--verify", "--json",
        ])
        self.assertEqual(code, 0)
        replay = json.loads(out)
        self.assertEqual(replay["event_count"], 8)
        self.assertTrue(replay["projection_digest"].startswith(""))

    def test_nonzero_exit_records_failed_terminal(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-fail", "run",
            "--", PY, "-c", "import sys; sys.exit(5)",
        ])
        self.assertEqual(code, 1)
        summary = json.loads(out)
        self.assertEqual(summary["terminal_status"], "failed")
        self.assertEqual(summary["exit_code"], 5)

        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-fail", "status", "--json",
        ])
        status = json.loads(out)
        self.assertEqual(status["terminal_status"], "failed")
        self.assertEqual(status["node_states"]["worker"], "failed")

    def test_timeout_records_failed_terminal_and_tree_kill(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-timeout", "run",
            "--timeout", "1.0", "--grace", "2.0",
            "--", PY, "-c", "import time; time.sleep(60)",
        ])
        self.assertEqual(code, 1)
        summary = json.loads(out)
        self.assertEqual(summary["terminal_status"], "failed")
        self.assertTrue(summary["timed_out"])
        self.assertTrue(summary["tree_kill_used"])

    def test_duplicate_run_id_is_rejected(self):
        args = [
            "--root", str(self.root), "--run-id", "run-dup", "run",
            "--", PY, "-c", "import sys; sys.exit(0)",
        ]
        code, _out, _err = _run_cli(args)
        self.assertEqual(code, 0)
        code2, _out2, err2 = _run_cli(args)
        self.assertEqual(code2, 2)
        self.assertIn("run_created", err2)

    def test_output_truncation_is_visible_in_run_summary(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-trunc", "run",
            "--max-stdout-bytes", "10",
            "--", PY, "-c", "import sys; sys.stdout.write('A' * 100000)",
        ])
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertTrue(summary["stdout_truncated"])

    def test_env_allowlist_drops_secret_looking_vars(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-env", "run",
            "--env", "MY_SECRET_TOKEN=shh", "--env", "MY_SAFE_VAR=ok",
            "--", PY, "-c", "import sys; sys.exit(0)",
        ])
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertIn("MY_SECRET_TOKEN", summary["dropped_env_keys"])

    def test_journal_records_the_actor_that_performed_each_action(self):
        code, out, _err = _run_cli([
            "--root", str(self.root), "--run-id", "run-actors", "run",
            "--", PY, "-c", "import sys; sys.exit(0)",
        ])
        self.assertEqual(code, 0)
        journal = Path(json.loads(out)["journal_file"])
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        observed = [(event["type"], event["actor"]["role"]) for event in events]
        self.assertEqual(observed, [
            ("run_created", "router"),
            ("graph_published", "router"),
            ("node_status_changed", "scheduler"),
            ("attempt_dispatched", "scheduler"),
            ("node_status_changed", "scheduler"),
            ("node_status_changed", "worker"),
            ("worker_finished", "worker"),
            ("node_status_changed", "worker"),
        ])


class CliModuleEntrypointTests(unittest.TestCase):
    def test_python_dash_m_graphori_core_cli_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PYTHONPATH": str(Path(__file__).parents[1] / "src")}
            import os
            full_env = dict(os.environ)
            full_env.update(env)
            result = subprocess.run(
                [PY, "-m", "graphori_core.cli", "--root", tmp, "--run-id", "run-mod",
                 "run", "--", PY, "-c", "import sys; sys.exit(0)"],
                capture_output=True, text=True, env=full_env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertIsNone(summary["terminal_status"])
            self.assertEqual(summary["execution_outcome"], "succeeded")


if __name__ == "__main__":
    unittest.main()
