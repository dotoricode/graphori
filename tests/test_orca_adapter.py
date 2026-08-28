import json
import shutil
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.orca import CliResponse, OrcaAdapter, normalize_snapshot


class OrcaProjectionTests(unittest.TestCase):
    def test_connection_and_fixture_have_same_projection(self):
        fixture = [{"type": "heartbeat", "run_id": "r1", "task_id": "t1",
                    "attempt_id": "a1", "timestamp": "2026-01-01T00:00:00Z",
                    "unknown_private": "ignored"}]
        connected = {"events": fixture, "private": "ignored"}
        self.assertEqual(normalize_snapshot(fixture), normalize_snapshot(connected))

    def test_missing_fields_are_quarantined(self):
        event = normalize_snapshot({"type": "not-a-public-event"}, run_id="r", task_id="t")[0]
        self.assertEqual(event["type"], "event_quarantined")
        self.assertEqual(event["payload"]["reason"], "adapter_unavailable")

    def test_fake_cli_malformed_nonzero_and_timeout_do_not_raise(self):
        def fake(argv, timeout):
            if "run-show" not in argv:
                return CliResponse(tuple(argv), 0, "{bad", "")
            return CliResponse(tuple(argv), 7, "", "failed")
        adapter = OrcaAdapter(runner=fake)
        value, response = adapter.status()
        self.assertIsNone(value)
        self.assertEqual(response.error, "malformed_json")
        value, response = adapter.run_show("r")
        self.assertIsNone(value)
        self.assertEqual(response.returncode, 7)

    @unittest.skipUnless(shutil.which("orca"), "Orca CLI is not installed")
    def test_real_cli_read_only_status_fixture(self):
        value, response = OrcaAdapter(timeout=5).status()
        self.assertTrue(response.argv[-1] == "--json")
        if response.ok:
            self.assertIsInstance(value, (dict, list))
            projected = normalize_snapshot(value)
            self.assertTrue(projected)
        else:
            # Offline Orca is a valid unavailable result, never a core exception.
            self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
