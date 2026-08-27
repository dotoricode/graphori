import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import canonical_event, ensure_run_dirs, submit_event, JournalWriter  # noqa: E402


class JournalMalformedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ensure_run_dirs(self.root, "run-malformed")
        self.writer = JournalWriter(self.paths)

    def test_invalid_json_ready_file_is_quarantined(self):
        (self.paths.ready / "bad.json").write_bytes(b"{not valid json")
        counts = self.writer.consume_ready()
        self.assertEqual(counts, {"accepted": 0, "duplicate": 0, "conflict": 0, "quarantined": 1})
        self.assertFalse((self.paths.ready / "bad.json").exists())
        quarantined = list(self.paths.quarantine_dir.glob("bad.json"))
        self.assertEqual(len(quarantined), 1)
        self.assertFalse(self.paths.journal_file.exists())

    def test_missing_required_field_is_quarantined(self):
        envelope = canonical_event("heartbeat", event_id="evt_1", run_id="run-malformed")
        envelope.pop("actor")
        import json
        (self.paths.ready / "missing_actor.json").write_text(
            json.dumps(envelope), encoding="utf-8")
        counts = self.writer.consume_ready()
        self.assertEqual(counts["quarantined"], 1)
        self.assertEqual(counts["accepted"], 0)

    def test_wrong_run_id_is_quarantined(self):
        envelope = canonical_event("heartbeat", event_id="evt_1", run_id="different-run")
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            envelope.pop(field, None)
        import json
        (self.paths.ready / "wrong_run.json").write_text(json.dumps(envelope), encoding="utf-8")
        counts = self.writer.consume_ready()
        self.assertEqual(counts["quarantined"], 1)

    def test_unknown_event_type_is_quarantined(self):
        envelope = canonical_event("heartbeat", event_id="evt_1", run_id="run-malformed")
        envelope["type"] = "not_a_real_event"
        for field in ("seq", "recorded_at", "prev_digest", "digest"):
            envelope.pop(field, None)
        import json
        (self.paths.ready / "unknown_type.json").write_text(json.dumps(envelope), encoding="utf-8")
        counts = self.writer.consume_ready()
        self.assertEqual(counts["quarantined"], 1)


if __name__ == "__main__":
    unittest.main()
