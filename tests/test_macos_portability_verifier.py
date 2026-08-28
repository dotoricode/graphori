import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


@unittest.skipUnless(sys.platform == "darwin", "macOS fixture requires macOS")
class MacOSPortabilityVerifierTests(unittest.TestCase):
    def test_fixture_emits_every_required_pass_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "macos-portability.json"
            result = subprocess.run(
                [sys.executable, "scripts/verify_macos_portability.py",
                 "--output", str(output)],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(
            {record["fixture"] for record in records},
            {
                "process_tree", "path_escape", "symlink", "case_collision",
                "jsonl_tmp_ready", "replay_idempotency",
            },
        )
        self.assertEqual({record["platform"] for record in records}, {"macos"})
        self.assertEqual({record["verdict"] for record in records}, {"pass"})
        for record in records:
            self.assertTrue(record["hash"].startswith("sha256:"))
            self.assertTrue(record["command"].startswith(sys.executable))
            self.assertEqual(
                record["hash"],
                "sha256:" + hashlib.sha256(record["evidence"].encode("utf-8")).hexdigest(),
            )
