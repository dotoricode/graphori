import sys
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import canonical_event, ensure_run_dirs, submit_event, JournalWriter  # noqa: E402


_PROCESS_PRODUCER = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from graphori_core import canonical_event, ensure_run_dirs, submit_event
from graphori_core import journal
journal.time.time_ns = lambda: 100
root, run_id, index = Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
paths = ensure_run_dirs(root, run_id)
event = canonical_event(
    "heartbeat", event_id=f"evt_{index}", run_id=run_id, actor_role="worker",
)
event["producer_event_id"] = f"producer:worker-{index}:1"
event["actor"] = {"role": "worker", "role_id": f"worker-{index}"}
for field in ("seq", "recorded_at", "prev_digest", "digest"):
    event.pop(field, None)
print(submit_event(paths, event, local_seq=1).name, flush=True)
'''


class JournalConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ensure_run_dirs(self.root, "run-concurrency")

    def test_ten_concurrent_producers_submit_distinct_events(self):
        def produce(index):
            envelope = canonical_event(
                "heartbeat", event_id=f"evt_{index}", run_id="run-concurrency",
                actor_role="worker", seq=0,
            )
            envelope["producer_event_id"] = f"producer:worker-{index}:1"
            envelope["actor"] = {"role": "worker", "role_id": f"worker-{index}"}
            for field in ("seq", "recorded_at", "prev_digest", "digest"):
                envelope.pop(field, None)
            return submit_event(self.paths, envelope, local_seq=1)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(produce, i) for i in range(10)]
            paths = [f.result() for f in as_completed(futures)]

        self.assertEqual(len(paths), 10)
        self.assertEqual(len(set(p.name for p in paths)), 10)
        self.assertEqual(len(list(self.paths.ready.iterdir())), 10)

        writer = JournalWriter(self.paths)
        counts = writer.consume_ready()
        self.assertEqual(counts, {"accepted": 10, "duplicate": 0, "conflict": 0, "quarantined": 0})

        journal_lines = self.paths.journal_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(journal_lines), 10)
        self.assertEqual(list(self.paths.ready.iterdir()), [])

        import json
        events = [json.loads(line) for line in journal_lines]
        seqs = [e["seq"] for e in events]
        self.assertEqual(seqs, list(range(10)))
        self.assertEqual(len({e["event_id"] for e in events}), 10)
        prev = "sha256:" + "0" * 64
        for event in events:
            self.assertEqual(event["prev_digest"], prev)
            prev = event["digest"]

    def test_processes_with_the_same_wall_time_receive_distinct_durable_ordinals(self):
        src = str(Path(__file__).parents[1] / "src")
        children = [
            subprocess.Popen(
                [sys.executable, "-c", _PROCESS_PRODUCER, src, str(self.root),
                 "run-process-concurrency", str(index)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            for index in range(8)
        ]
        names = []
        for child in children:
            stdout, stderr = child.communicate(timeout=20)
            self.assertEqual(child.returncode, 0, stderr)
            names.append(stdout.strip())

        ordinals = [int(name.split(".", 1)[0]) for name in names]
        self.assertEqual(len(set(ordinals)), 8)
        self.assertEqual(sorted(ordinals), list(range(100, 108)))


if __name__ == "__main__":
    unittest.main()
