import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import canonical_event, ensure_run_dirs, submit_event, JournalWriter  # noqa: E402


class JournalIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ensure_run_dirs(self.root, "run-idem")
        self.writer = JournalWriter(self.paths)
        self.addCleanup(self.writer.close)

    def _envelope(self, *, payload):
        envelope = canonical_event("heartbeat", event_id="evt_1", run_id="run-idem",
                                    actor_role="worker", payload=payload)
        envelope["producer_event_id"] = "producer:worker-1:1"
        envelope["actor"] = {"role": "worker", "role_id": "worker-1"}
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            envelope.pop(field, None)
        return envelope

    def _journal_events(self):
        return [json.loads(line) for line in
                self.paths.journal_file.read_text(encoding="utf-8").splitlines()]

    def test_exact_duplicate_producer_event_id_is_ignored(self):
        envelope = self._envelope(payload={"note": "first"})
        submit_event(self.paths, envelope, local_seq=1)
        self.writer.consume_ready()
        first_events = self._journal_events()
        self.assertEqual(len(first_events), 1)

        submit_event(self.paths, dict(envelope), local_seq=2)
        counts = self.writer.consume_ready()
        self.assertEqual(counts["duplicate"], 1)
        self.assertEqual(counts["accepted"], 0)
        self.assertEqual(self._journal_events(), first_events)
        self.assertEqual(list(self.paths.quarantine_dir.iterdir()), [])

    def test_conflicting_duplicate_is_quarantined_and_never_overwrites_accepted(self):
        envelope = self._envelope(payload={"note": "first"})
        submit_event(self.paths, envelope, local_seq=1)
        self.writer.consume_ready()
        accepted = self._journal_events()
        self.assertEqual(len(accepted), 1)

        conflicting = self._envelope(payload={"note": "different"})
        submit_event(self.paths, conflicting, local_seq=2)
        counts = self.writer.consume_ready()
        self.assertEqual(counts["conflict"], 1)
        self.assertEqual(counts["accepted"], 0)

        # The original accepted entry must be byte-for-byte unchanged.
        self.assertEqual(self._journal_events(), accepted)
        quarantined = list(self.paths.quarantine_dir.glob("*.json"))
        self.assertEqual(len(quarantined), 1)
        reason = quarantined[0].with_suffix(quarantined[0].suffix + ".reason.txt").read_text()
        self.assertIn("idempotency_conflict", reason)

    def test_same_event_id_different_producer_event_id_conflicts(self):
        envelope = self._envelope(payload={"note": "first"})
        submit_event(self.paths, envelope, local_seq=1)
        self.writer.consume_ready()
        accepted = self._journal_events()

        conflicting = self._envelope(payload={"note": "different"})
        conflicting["producer_event_id"] = "producer:worker-1:2"
        submit_event(self.paths, conflicting, local_seq=2)
        counts = self.writer.consume_ready()
        self.assertEqual(counts["conflict"], 1)
        self.assertEqual(self._journal_events(), accepted)

    def test_exact_duplicate_remains_idempotent_after_writer_restart(self):
        envelope = self._envelope(payload={"note": "persisted"})
        submit_event(self.paths, envelope, local_seq=1)
        self.writer.consume_ready()
        accepted = self._journal_events()

        self.writer.close()
        restarted = JournalWriter(self.paths)
        self.addCleanup(restarted.close)
        submit_event(self.paths, dict(envelope), local_seq=2)
        counts = restarted.consume_ready()

        self.assertEqual(counts["duplicate"], 1)
        self.assertEqual(counts["conflict"], 0)
        self.assertEqual(self._journal_events(), accepted)


if __name__ == "__main__":
    unittest.main()
