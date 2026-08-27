import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import EvidenceStore, ensure_run_dirs  # noqa: E402


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ensure_run_dirs(self.root, "run-evidence")
        self.store = EvidenceStore(self.paths)

    def test_put_is_content_addressed_and_ignores_caller_filename(self):
        data = b"hello graphori"
        evidence_id = self.store.put(data, label="../../evil.txt")
        self.assertTrue(evidence_id.startswith("ev_sha256_"))
        import hashlib
        self.assertEqual(evidence_id, f"ev_sha256_{hashlib.sha256(data).hexdigest()}")
        self.assertEqual(self.store.get(evidence_id), data)

        manifest = self.store.manifest()
        entry = manifest[evidence_id]
        # The unsafe label is sanitized and never used as a storage path.
        self.assertNotIn("..", entry["labels"][0])
        object_files = list((self.paths.evidence_dir / "objects").glob("*.bin"))
        self.assertEqual(len(object_files), 1)
        self.assertNotIn("evil", object_files[0].name)

    def test_identical_content_deduplicates_to_one_object(self):
        id_a = self.store.put(b"same bytes")
        id_b = self.store.put(b"same bytes", label="second-call")
        self.assertEqual(id_a, id_b)
        object_files = list((self.paths.evidence_dir / "objects").glob("*.bin"))
        self.assertEqual(len(object_files), 1)

    def test_unknown_evidence_id_raises(self):
        with self.assertRaises(KeyError):
            self.store.get("ev_sha256_" + "0" * 64)


if __name__ == "__main__":
    unittest.main()
