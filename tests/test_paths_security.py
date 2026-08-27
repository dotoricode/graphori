import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_core import PathSecurityError, ensure_run_dirs, safe_join  # noqa: E402
from graphori_core.paths import resolve_run_root  # noqa: E402


class PathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = resolve_run_root(Path(self.tmp.name))

    def test_relative_traversal_is_rejected(self):
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, "..", "escape.txt")
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, "a/../../b")
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, "a", "..", "..", "b")

    def test_absolute_and_drive_relative_and_unc_escape_is_rejected(self):
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, "C:\\Windows\\System32\\evil.txt")
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, "\\\\server\\share\\evil.txt")
        with self.assertRaises(PathSecurityError):
            safe_join(self.root, str(self.root.parent / "outside.txt"))

    def test_case_collision_ambiguity_is_rejected(self):
        paths = ensure_run_dirs(self.root, "run-case")
        (paths.ready / "Producer.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(PathSecurityError):
            safe_join(paths.ready, "producer.json")
        with self.assertRaises(PathSecurityError):
            safe_join(paths.ready, "PRODUCER.JSON")

    def test_junction_escape_is_rejected_or_deferred_without_privilege(self):
        paths = ensure_run_dirs(self.root, "run-junction")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        link = paths.run_root / "escape_link"

        if sys.platform != "win32":
            self.skipTest("junction fixture is Windows-only; deferred/unknown on this platform")

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), outside.name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest(
                f"deferred: could not create a junction in this environment "
                f"(rc={result.returncode}, stderr={result.stderr.strip()})"
            )
        self.addCleanup(lambda: link.exists() and link.rmdir())

        with self.assertRaises(PathSecurityError):
            safe_join(self.root, ".graphori", "runs", "run-junction", "escape_link", "evil.txt")


if __name__ == "__main__":
    unittest.main()
