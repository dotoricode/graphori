import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    Node, NodeKind, NodeState, Run, StateReducer, StateTransitionError, Task,
    TerminalStatus, Usage, UsageStatus, canonical_event,
)


def event(event_type, *, actor="router", payload=None, entity=None, **extra):
    return canonical_event(event_type, actor_role=actor, payload=payload, entity=entity, **extra)


class PlatformAndFailureContractTests(unittest.TestCase):
    def _published(self, run_id, node_state=NodeState.PENDING):
        task = Task(f"task-{run_id}", "x", run_id=run_id, graph_version=1)
        run = Run(run_id, graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "worker", state=node_state))
        reducer = StateReducer(task, run)
        reducer.apply(event("run_created", run_id=run_id, task_id=task.task_id, seq=1))
        reducer.apply(event("graph_published", run_id=run_id, task_id=task.task_id, seq=2))
        return task, run, reducer

    def test_windows_pass_and_macos_deferred_never_becomes_a_global_success(self):
        task, run, reducer = self._published("run-partial-platform")
        reducer.apply(event("platform_verdict_recorded", run_id=run.run_id, task_id=task.task_id,
                            payload={"platform": "windows", "status": "pass",
                                     "fixture_id": "fx-1", "evidence_id": "ev-1"}, seq=3))
        reducer.apply(event("platform_verdict_recorded", run_id=run.run_id, task_id=task.task_id,
                            payload={"platform": "macos", "status": "deferred"}, seq=4))
        summary = reducer.platform_summary()
        self.assertEqual(summary["scope"], "windows")
        self.assertEqual(summary["exclusions"], ["macos"])

        # A platform pass is not execution success: the worker node is still
        # pending, so run_terminal(succeeded) must still be rejected.
        with self.assertRaises(StateTransitionError):
            reducer.apply(event("run_terminal", run_id=run.run_id, task_id=task.task_id,
                                seq=5, payload={"terminal_status": "succeeded"}))
        self.assertIsNone(run.terminal_status)

    def test_failure_fixtures_never_auto_promote_to_pass(self):
        for state in (NodeState.FAILED, NodeState.BLOCKED, NodeState.REJECTED,
                      NodeState.INCONCLUSIVE, NodeState.CANCELLED):
            with self.subTest(state=state):
                task, run, reducer = self._published(f"run-fail-{state.value}", node_state=state)
                with self.assertRaises(StateTransitionError):
                    reducer.apply(event("run_terminal", run_id=run.run_id, task_id=task.task_id,
                                        seq=3, payload={"terminal_status": "succeeded"}))
                self.assertIsNone(run.terminal_status)
                # The only terminal each non-passed fixture may legitimately
                # reach is a non-success one, never succeeded.
                reducer.apply(event("run_terminal", run_id=run.run_id, task_id=task.task_id,
                                    seq=4, payload={"terminal_status": "failed"}))
                self.assertEqual(run.terminal_status, TerminalStatus.FAILED)


class UsageStatusContractTests(unittest.TestCase):
    def test_known_estimate_and_unknown_are_distinct_and_unknown_is_not_zero(self):
        known = Usage(UsageStatus.KNOWN, input_tokens=10, output_tokens=5)
        estimate = Usage(UsageStatus.ESTIMATE, predicted_tokens=7)
        unknown = Usage(UsageStatus.UNKNOWN)
        self.assertEqual(known.total_tokens, 15)
        self.assertTrue(known.is_known)
        self.assertEqual(estimate.total_tokens, 7)
        self.assertFalse(estimate.is_known)
        self.assertIsNone(unknown.total_tokens)
        self.assertFalse(unknown.is_known)

    def test_usage_recorded_event_shape_is_validated_by_canonical_envelope(self):
        good = canonical_event("usage_recorded", payload={
            "usage": {"status": "known", "input_tokens": 1, "output_tokens": 2}})
        good["usage"] = {"status": "known", "input_tokens": 1, "output_tokens": 2}
        from graphori_core import validate_event_envelope
        validate_event_envelope(good)  # does not raise
        bad = dict(good)
        bad["usage"] = "not-an-object"
        with self.assertRaises(StateTransitionError):
            validate_event_envelope(bad)


if __name__ == "__main__":
    unittest.main()
