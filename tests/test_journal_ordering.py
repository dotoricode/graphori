import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    JournalWriter,
    StateTransitionError,
    canonical_event,
    ensure_run_dirs,
    submit_event,
)
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
        copy_root = self.root / "copied"
        paths_b = ensure_run_dirs(copy_root, "run-order-a")
        for index, source in enumerate(sorted(paths_a.ready.iterdir()), 1):
            destination = paths_b.ready / source.name
            shutil.copy2(source, destination)
            # The stamped protocol must not consult copied mtimes.
            os.utime(destination, ns=(index, 10_000 - index))

        writer_a = JournalWriter(paths_a)
        self.addCleanup(writer_a.close)
        writer_a.consume_ready()
        events_a = [json.loads(line) for line in
                    paths_a.journal_file.read_text(encoding="utf-8").splitlines()]

        writer_b = JournalWriter(paths_b)
        self.addCleanup(writer_b.close)
        writer_b.consume_ready()
        events_b = [json.loads(line) for line in
                    paths_b.journal_file.read_text(encoding="utf-8").splitlines()]

        order_a = [e["event_id"] for e in events_a]
        order_b = [e["event_id"] for e in events_b]
        # Both writers consumed byte-identical ready files. Changed mtimes and
        # a different directory listing cannot change their seq assignment.
        self.assertEqual(order_a, order_b)
        self.assertEqual(sorted(order_a), [f"evt_{i}" for i in range(10)])
        self.assertEqual([e["seq"] for e in events_a], list(range(10)))


    def test_ready_names_carry_the_submission_order_they_are_sorted_by(self):
        with mock.patch.object(journal.time, "time_ns", return_value=100):
            paths = self._seed_ready("run-order-stamped")
        names = sorted(path.name for path in paths.ready.iterdir())
        self.assertEqual(len(names), 10)
        for name in names:
            self.assertIsNotNone(
                journal._submission_ordinal(Path(name)),
                f"{name} carries no submission stamp",
            )
        # Sorting the names must reproduce submission order: producer worker-00
        # submitted fourth, so it cannot sort first merely by being worker-00.
        stamps = [journal._submission_ordinal(Path(name)) for name in names]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(len(set(stamps)), 10)

        writer = JournalWriter(paths)
        self.addCleanup(writer.close)
        writer.consume_ready()
        events = [
            json.loads(line)
            for line in paths.journal_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [event["event_id"] for event in events],
            [f"evt_{index}" for index in (7, 2, 9, 0, 5, 3, 8, 1, 6, 4)],
        )

    def test_wall_clock_rollback_cannot_reverse_one_producers_events(self):
        paths = ensure_run_dirs(self.root, "run-order-clock-rollback")

        def submit(event_id, local_seq):
            envelope = canonical_event(
                "heartbeat", event_id=event_id,
                run_id="run-order-clock-rollback", actor_role="worker",
            )
            envelope["producer_event_id"] = f"producer:worker:{local_seq}"
            envelope["actor"] = {"role": "worker", "role_id": "worker"}
            for field in ("seq", "recorded_at", "prev_digest", "digest"):
                envelope.pop(field, None)
            return submit_event(paths, envelope, local_seq=local_seq)

        with mock.patch.object(journal.time, "time_ns", side_effect=(200, 100)):
            first = submit("evt_first", 1)
            second = submit("evt_second", 2)

        self.assertLess(journal._submission_ordinal(first), journal._submission_ordinal(second))
        writer = JournalWriter(paths)
        self.addCleanup(writer.close)
        writer.consume_ready()
        events = [
            json.loads(line)
            for line in paths.journal_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([event["event_id"] for event in events], ["evt_first", "evt_second"])

    def test_corrupt_submission_counter_fails_closed(self):
        paths = ensure_run_dirs(self.root, "run-order-corrupt-counter")
        paths.submission_counter_file.write_text("not-an-integer\n", encoding="ascii")
        envelope = canonical_event(
            "heartbeat", event_id="evt_corrupt_counter",
            run_id="run-order-corrupt-counter", actor_role="worker",
        )
        envelope["producer_event_id"] = "producer:worker:1"
        envelope["actor"] = {"role": "worker", "role_id": "worker"}
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            envelope.pop(field, None)

        with self.assertRaisesRegex(StateTransitionError, "submission counter is corrupt"):
            submit_event(paths, envelope, local_seq=1)
        self.assertEqual(list(paths.ready.iterdir()), [])

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
        self.assertIsNone(journal._submission_ordinal(legacy))
        os.utime(legacy, ns=(1_000, 1_000))
        paths.submission_counter_file.unlink()

        newer = canonical_event(
            "heartbeat", event_id="evt_new", run_id="run-order-legacy",
            actor_role="worker",
        )
        newer["producer_event_id"] = "producer:new:1"
        newer["actor"] = {"role": "worker", "role_id": "new"}
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            newer.pop(field, None)
        with mock.patch.object(journal.time, "time_ns", return_value=100):
            new_path = submit_event(paths, newer, local_seq=1)
        self.assertGreater(journal._submission_ordinal(new_path), 1_000)

        writer = JournalWriter(paths)
        self.addCleanup(writer.close)
        counts = writer.consume_ready()

        self.assertEqual(counts["accepted"], 2)
        self.assertEqual(counts["quarantined"], 0)
        events = [
            json.loads(line)
            for line in paths.journal_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([event["event_id"] for event in events], ["evt_legacy", "evt_new"])


if __name__ == "__main__":
    unittest.main()
