import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class QuickstartDocsTests(unittest.TestCase):
    """Wherever a `graphori` quickstart appears, it must quote the run root."""

    def test_windows_quickstarts_store_absolute_root(self):
        documents = (ROOT / "docs" / "public" / "INSTALL.md",
                     ROOT / "docs" / "archive" / "verification" / "I10_INSTALLABLE_SKILL_BUILD.md")
        for path in documents:
            text = path.read_text(encoding="utf-8")
            self.assertIn("$root = (Get-Location).Path", text, path)
            self.assertNotIn("--root .", text, path)
            self.assertNotRegex(text, r"--root\s+\(Get-Location\)\.Path", path)
            self.assertRegex(text, r"--root\s+\$root\b", path)

    def test_posix_quickstarts_quote_pwd_p_root(self):
        documents = (ROOT / "docs" / "public" / "INSTALL.md",
                     ROOT / "docs" / "archive" / "verification" / "I10_INSTALLABLE_SKILL_BUILD.md")
        for path in documents:
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r'repo_root="\$\(pwd -P\)"', path)
            self.assertRegex(text, r'--root\s+"\$repo_root"', path)
            self.assertNotRegex(text, r'--root\s+\$repo_root\b', path)


if __name__ == "__main__":
    unittest.main()
