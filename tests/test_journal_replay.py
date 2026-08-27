import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    Graph, Node, NodeKind, Run, StateReducer, canonical_event, ensure_run_dirs,
    replay_journal, submit_event, JournalWriter,
)


def _strip_writer_fields(envelope):
    for field in ("seq", "recorded_at", "prev_digest", "digest"):
        envelope.pop(field, None)
    return envelope


class JournalReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run_id = "run-replay"
        self.paths = ensure_run_dirs(self.root, self.run_id)

    def _submit(self, event_type, *, actor_role, seq_hint, payload=None, entity=None):
        envelope = canonical_event(event_type, event_id=f"evt_{seq_hint}", run_id=self.run_id,
                                    task_id="task-replay", actor_role=actor_role,
                                    payload=payload, entity=entity)
        envelope["producer_event_id"] = f"producer:{actor_role}:{seq_hint}"
        _strip_writer_fields(envelope)
        submit_event(self.paths, envelope, local_seq=seq_hint)

    def _build_lifecycle_journal(self):
        self._submit("run_created", actor_role="router", seq_hint=1)
        self._submit("graph_published", actor_role="router", seq_hint=2)
        statuses = ("ready", "assigned", "running", "awaiting_verification", "passed")
        actors = ("scheduler", "scheduler", "worker", "worker", "verifier")
        for index, (actor, status) in enumerate(zip(actors, statuses), start=3):
            self._submit("node_status_changed", actor_role=actor, seq_hint=index,
                         entity={"node_id": "worker"}, payload={"status": status})
        self._submit("run_terminal", actor_role="router", seq_hint=8,
                     payload={"terminal_status": "succeeded"})
        writer = JournalWriter(self.paths)
        counts = writer.consume_ready()
        self.assertEqual(counts["accepted"], 8)

    def _apply_via_reducer(self, events):
        from graphori_core import Task
        task = Task("task-replay", "replay", run_id=self.run_id, graph_version=1)
        run = Run(self.run_id, graph_version=1)
        run.graph.add_node(Node("worker", NodeKind.WORKER, "worker"))
        reducer = StateReducer(task, run)
        for event in events:
            reducer.apply(event)
        return run.terminal_status, run.graph.nodes["worker"].state

    def test_replay_hash_chain_and_projection_digest_are_reproducible(self):
        self._build_lifecycle_journal()

        events_first, digest_first = replay_journal(self.paths)
        events_second, digest_second = replay_journal(self.paths)

        self.assertEqual(len(events_first), 8)
        self.assertEqual(digest_first, digest_second)
        self.assertEqual(events_first, events_second)

        # Reuse the existing reducer contract (not a second truth store) to
        # confirm the replayed event stream reconstructs the same terminal
        # projection both times.
        terminal_1, node_state_1 = self._apply_via_reducer(events_first)
        terminal_2, node_state_2 = self._apply_via_reducer(events_second)
        self.assertEqual(terminal_1, terminal_2)
        self.assertEqual(node_state_1, node_state_2)
        self.assertEqual(terminal_1.value, "succeeded")


if __name__ == "__main__":
    unittest.main()
