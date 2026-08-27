"""Real multi-process ownership tests for disposable Graphori run roots."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import (  # noqa: E402
    JournalOwnershipError, JournalWriter, canonical_event, ensure_run_dirs,
    replay_journal, submit_event,
)


_CHILD = r'''
import os
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from graphori_core import JournalOwnershipError, JournalWriter, canonical_event, ensure_run_dirs, submit_event

root = Path(sys.argv[2])
run_id = sys.argv[3]
mode = sys.argv[4]
paths = ensure_run_dirs(root, run_id)
if mode == "crash":
    writer = JournalWriter(paths)
    os._exit(0)
if mode == "contend":
    try:
        JournalWriter(paths)
    except JournalOwnershipError as exc:
        print(str(exc), flush=True)
        raise SystemExit(23)
    raise SystemExit(99)
writer = JournalWriter(paths)
event = canonical_event("heartbeat", event_id="held-event", run_id=run_id, actor_role="worker")
event["producer_event_id"] = "producer:owner:1"
event["actor"] = {"role": "worker", "role_id": "owner"}
for name in ("seq", "recorded_at", "prev_digest", "digest"):
    event.pop(name, None)
submit_event(paths, event, local_seq=1)
writer.consume_ready()
print("owned", flush=True)
sys.stdin.readline()
writer.close()
'''


@unittest.skipUnless(os.name == "posix", "POSIX flock writer ownership fixture")
class JournalWriterOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = str(Path(__file__).parents[1] / "src")

    def _child(self, run_id, mode):
        return subprocess.Popen(
            [sys.executable, "-c", _CHILD, self.src, str(self.root), run_id, mode],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )

    def _release(self, child):
        child.stdin.write("release\n")
        child.stdin.flush()
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr or stdout)

    def test_same_run_has_one_owner_and_contender_never_appends(self):
        owner = self._child("run-one", "hold")
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        self.assertEqual(owner.stdout.readline().strip(), "owned")

        contender = subprocess.run(
            [sys.executable, "-c", _CHILD, self.src, str(self.root), "run-one", "contend"],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(contender.returncode, 23)
        self.assertIn("다른 Graphori에서 실행 중", contender.stdout)
        self.assertIn("실행 기록은 변경하지 않았습니다", contender.stdout)

        paths = ensure_run_dirs(self.root, "run-one")
        raw_before = paths.journal_file.read_bytes()
        self.assertEqual(len(raw_before.splitlines()), 1)
        self._release(owner)

        # The failed contender did not append a byte, and the chain still replays.
        self.assertEqual(paths.journal_file.read_bytes(), raw_before)
        first_events, first_digest = replay_journal(paths)
        second_events, second_digest = replay_journal(paths)
        self.assertEqual(len(first_events), 1)
        self.assertEqual(first_events, second_events)
        self.assertEqual(first_digest, second_digest)

    def test_different_runs_can_hold_writer_ownership_in_parallel(self):
        owner = self._child("run-a", "hold")
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        self.assertEqual(owner.stdout.readline().strip(), "owned")
        other = JournalWriter(ensure_run_dirs(self.root, "run-b"))
        self.addCleanup(other.close)
        self._release(owner)

    def test_crashed_owner_releases_os_lock_for_recovery(self):
        crashed = self._child("run-crash", "crash")
        _, stderr = crashed.communicate(timeout=10)
        self.assertEqual(crashed.returncode, 0, stderr)
        writer = JournalWriter(ensure_run_dirs(self.root, "run-crash"))
        self.addCleanup(writer.close)

    def test_clean_close_releases_ownership_without_removing_lock_inode(self):
        paths = ensure_run_dirs(self.root, "run-clean-close")
        writer = JournalWriter(paths)
        lock_file = paths.writer_lock_file
        writer.close()
        recovered = JournalWriter(paths)
        self.addCleanup(recovered.close)
        self.assertTrue(lock_file.exists())


if __name__ == "__main__":
    unittest.main()
