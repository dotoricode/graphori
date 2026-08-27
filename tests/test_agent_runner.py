import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    AgentRunner, Attempt, AttemptState, NodeKind, ProcessLimits, ProcessSupervisor, Role,
)

PY = sys.executable


class AgentRunnerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner = AgentRunner(ProcessSupervisor())

    def _attempt(self, attempt_id: str) -> Attempt:
        return Attempt(attempt_id, "task-x", Role("role_worker", NodeKind.WORKER, "worker"))

    def test_successful_attempt_reaches_succeeded(self):
        attempt = self._attempt("attempt-ok")
        outcome = self.runner.run_attempt(
            attempt, argv=[PY, "-c", "import sys; sys.exit(0)"], workspace_root=self.root,
        )
        self.assertEqual(attempt.state, AttemptState.SUCCEEDED)
        self.assertEqual(outcome.process.exit_code, 0)
        payload = outcome.worker_finished_payload()
        self.assertEqual(payload["attempt_state"], "succeeded")
        self.assertFalse(payload["timed_out"])

    def test_nonzero_exit_reaches_failed(self):
        attempt = self._attempt("attempt-fail")
        outcome = self.runner.run_attempt(
            attempt, argv=[PY, "-c", "import sys; sys.exit(3)"], workspace_root=self.root,
        )
        self.assertEqual(attempt.state, AttemptState.FAILED)
        self.assertEqual(outcome.process.exit_code, 3)

    def test_timeout_reaches_outcome_unknown(self):
        attempt = self._attempt("attempt-timeout")
        limits = ProcessLimits(timeout_seconds=1.0, grace_seconds=2.0)
        outcome = self.runner.run_attempt(
            attempt, argv=[PY, "-c", "import time; time.sleep(60)"], workspace_root=self.root,
            limits=limits,
        )
        self.assertEqual(attempt.state, AttemptState.OUTCOME_UNKNOWN)
        self.assertTrue(outcome.process.timed_out)
        self.assertTrue(outcome.process.tree_kill_used)

    def test_stdout_stderr_are_digested_not_embedded_raw(self):
        attempt = self._attempt("attempt-digest")
        outcome = self.runner.run_attempt(
            attempt, argv=[PY, "-c", "import sys; sys.stdout.write('secret-looking-output')"],
            workspace_root=self.root,
        )
        payload = outcome.worker_finished_payload()
        self.assertNotIn("secret-looking-output", str(payload))
        self.assertEqual(len(payload["stdout_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
