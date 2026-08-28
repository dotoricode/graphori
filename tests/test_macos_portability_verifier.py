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
            raw_evidence = output.read_text(encoding="utf-8")
            self.assertNotIn(str(Path.home()), raw_evidence)
            records = json.loads(raw_evidence)

        self.assertEqual(
            {record["fixture"] for record in records},
            {
                "process_tree", "path_escape", "symlink", "case_collision",
                "jsonl_tmp_ready", "replay_idempotency", "generic_adapter_lifecycle",
            },
        )
        self.assertEqual({record["platform"] for record in records}, {"macos"})
        self.assertEqual({record["verdict"] for record in records}, {"pass"})
        for record in records:
            self.assertTrue(record["hash"].startswith("sha256:"))
            self.assertTrue(record["command"].startswith("python -m unittest"))
            self.assertNotIn(str(Path.home()), record["command"])
            self.assertRegex(record["python"], r"^CPython 3\.\d+\.\d+")
            canonical_record = {
                key: value for key, value in record.items() if key != "hash"
            }
            canonical = json.dumps(
                canonical_record, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self.assertEqual(
                record["hash"], "sha256:" + hashlib.sha256(canonical).hexdigest(),
            )
