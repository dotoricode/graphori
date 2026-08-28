import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import canonical_event, ensure_run_dirs, submit_event, JournalWriter  # noqa: E402
from graphori_core import journal  # noqa: E402


class JournalOrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _seed_ready(self, run_id):
        paths = ensure_run_dirs(self.root, run_id)
        # Submit out of "natural" numeric order to prove ordering does not
        # depend on wall-clock arrival: producer ids are shuffled here.
        for index in (7, 2, 9, 0, 5, 3, 8, 1, 6, 4):
            envelope = canonical_event(
                "heartbeat", event_id=f"evt_{index}", run_id=run_id, actor_role="worker",
            )
            envelope["producer_event_id"] = f"producer:worker-{index:02d}:1"
            envelope["actor"] = {"role": "worker", "role_id": f"worker-{index:02d}"}
            for field in ("seq", "recorded_at", "prev_digest", "digest"):
                envelope.pop(field, None)
            submit_event(paths, envelope, local_seq=1)
        return paths

    def test_ready_ordering_is_a_deterministic_function_of_filenames(self):
        paths_a = self._seed_ready("run-order-a")
        writer_a = JournalWriter(paths_a)
        writer_a.consume_ready()
        events_a = [json.loads(line) for line in
                    paths_a.journal_file.read_text(encoding="utf-8").splitlines()]

        # Re-run consumption on a fresh copy of the exact same ready set and
        # confirm identical seq assignment, independent of directory listing
        # order or timing.
        paths_b = self._seed_ready("run-order-b")
        writer_b = JournalWriter(paths_b)
        writer_b.consume_ready()
        events_b = [json.loads(line) for line in
                    paths_b.journal_file.read_text(encoding="utf-8").splitlines()]

        order_a = [e["event_id"] for e in events_a]
        order_b = [e["event_id"] for e in events_b]
        # Both runs submitted in the same shuffled sequence, so both must
        # reproduce that same submission-arrival order and the same seq
        # assignment -- the point being that re-running consumption is a
        # deterministic function of the ready set, not of listdir order.
        self.assertEqual(order_a, order_b)
        self.assertEqual(sorted(order_a), [f"evt_{i}" for i in range(10)])
        self.assertEqual([e["seq"] for e in events_a], list(range(10)))


    def test_ready_names_carry_the_submission_order_they_are_sorted_by(self):
        paths = self._seed_ready("run-order-stamped")
        names = sorted(path.name for path in paths.ready.iterdir())
        self.assertEqual(len(names), 10)
        for name in names:
            self.assertIsNotNone(
                journal._submitted_at(Path(name)),
                f"{name} carries no submission stamp",
            )
        # Sorting the names must reproduce submission order: producer worker-00
        # submitted fourth, so it cannot sort first merely by being worker-00.
        stamps = [journal._submitted_at(Path(name)) for name in names]
        self.assertEqual(stamps, sorted(stamps))

    def test_a_file_left_by_an_older_version_is_still_consumed(self):
        paths = ensure_run_dirs(self.root, "run-order-legacy")
        envelope = canonical_event(
            "heartbeat", event_id="evt_legacy", run_id="run-order-legacy",
            actor_role="worker",
        )
        envelope["producer_event_id"] = "producer:legacy:1"
        envelope["actor"] = {"role": "worker", "role_id": "legacy"}
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            envelope.pop(field, None)
        submitted = submit_event(paths, envelope, local_seq=1)
        # Strip the stamp to reproduce a name written before this change.
        legacy = submitted.rename(
            submitted.with_name(submitted.name.split(".", 1)[1]),
        )
        self.assertIsNone(journal._submitted_at(legacy))

        writer = JournalWriter(paths)
        self.addCleanup(writer.close)
        counts = writer.consume_ready()

        self.assertEqual(counts["accepted"], 1)
        self.assertEqual(counts["quarantined"], 0)


if __name__ == "__main__":
    unittest.main()
