import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import verify_macos_portability


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

    def test_failed_fixture_is_written_before_the_command_returns_nonzero(self):
        failed_record = {
            "platform": "macos", "fixture": "process_tree", "verdict": "fail",
            "evidence_id": "macos:process_tree:test", "command": "python -m unittest test",
            "host": "test-host", "python": "CPython 3.14.0", "evidence": "failure",
            "hash": "sha256:test",
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failed.json"
            with (
                mock.patch.object(
                    verify_macos_portability, "run_fixture",
                    return_value=failed_record,
                ),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                result = verify_macos_portability.main(["--output", str(output)])
            records = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertEqual(len(records), len(verify_macos_portability.FIXTURES))
        self.assertEqual({record["verdict"] for record in records}, {"fail"})
