import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    StateTransitionError, canonical_event, ensure_run_dirs, submit_event, JournalWriter,
)


def _strip_writer_fields(envelope):
    for field in ("seq", "recorded_at", "prev_digest", "digest"):
        envelope.pop(field, None)
    return envelope


class JournalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ensure_run_dirs(self.root, "run-recovery")

    def _write_valid_entries(self, count):
        for index in range(count):
            envelope = canonical_event("heartbeat", event_id=f"evt_{index}", run_id="run-recovery",
                                       actor_role="worker")
            envelope["producer_event_id"] = f"producer:worker:{index}"
            envelope["actor"] = {"role": "worker", "role_id": "worker"}
            _strip_writer_fields(envelope)
            submit_event(self.paths, envelope, local_seq=index)
        writer = JournalWriter(self.paths)
        writer.consume_ready()
        return writer

    def test_truncated_last_line_preserves_valid_prefix_and_quarantines_tail(self):
        writer = self._write_valid_entries(3)
        # Simulate a crash mid-write: append a partial, newline-less JSON
        # fragment as the new final line.
        with open(self.paths.journal_file, "ab") as handle:
            handle.write(b'{"schema_version": 1, "event_id": "evt_trunc' )

        writer.close()
        writer = JournalWriter(self.paths)  # triggers recovery on load
        lines = self.paths.journal_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            json.loads(line)  # still parseable, unmodified prefix

        quarantined = list(self.paths.quarantine_dir.glob("truncated_tail*.bin"))
        self.assertEqual(len(quarantined), 1)
        self.assertIn(b"evt_trunc", quarantined[0].read_bytes())
        self.assertEqual(writer.next_seq, 3)

        # The writer must still be usable afterwards.
        envelope = canonical_event("heartbeat", event_id="evt_after", run_id="run-recovery",
                                   actor_role="worker")
        envelope["producer_event_id"] = "producer:worker:after"
        envelope["actor"] = {"role": "worker", "role_id": "worker"}
        _strip_writer_fields(envelope)
        submit_event(self.paths, envelope, local_seq=99)
        counts = writer.consume_ready()
        self.assertEqual(counts["accepted"], 1)

    def test_corrupted_middle_line_fails_closed(self):
        self._write_valid_entries(4)
        lines = self.paths.journal_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 4)
        broken = dict(json.loads(lines[1]))
        broken["digest"] = "sha256:" + "f" * 64  # tamper without recomputing the hash
        lines[1] = json.dumps(broken)
        self.paths.journal_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with self.assertRaises(StateTransitionError):
            JournalWriter(self.paths)

        # The damaged journal must not be silently rewritten or approved.
        self.assertIn("evt_1", self.paths.journal_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
