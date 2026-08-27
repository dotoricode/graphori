"""Tests for the docs/DOCS_VIEWER.html readability & path-safety contract.

DOCS_VIEWER.html is a client-side (browser) JavaScript file. The Python
standard library has no JavaScript engine, so these tests do not execute
the script. Instead they:

  1. Extract the actual path-allowlist regex and guard clauses from the
     shipped HTML source (so the test tracks the real file, not a copy
     that could silently drift out of sync).
  2. Re-run the same rule set natively in Python against a large table of
     malicious and legitimate paths to prove the *rule set itself* is
     sound (defense in depth).
  3. Assert the required CSS/rendering contract tokens (white background,
     dark #172033 text, code/table/link/heading/list styling, long-line
     wrapping, UTF-8 charset) are present in the shipped file.
  4. Assert PROCESS_VIEW.html reuses the shared viewer instead of
     duplicating the renderer.
  5. Assert none of the tracked docs/**/*.md files contain inline
     color/style HTML (the readability bug must be fixed in the viewer,
     not by hard-coding colors into the Markdown source).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
VIEWER_PATH = DOCS_DIR / "DOCS_VIEWER.html"
PROCESS_VIEW_PATH = DOCS_DIR / "PROCESS_VIEW.html"


def _read(path):
    return path.read_text(encoding="utf-8")


class ViewerFilesExistTest(unittest.TestCase):
    def test_docs_viewer_exists(self):
        self.assertTrue(VIEWER_PATH.is_file(), "docs/DOCS_VIEWER.html is missing")

    def test_process_view_exists(self):
        self.assertTrue(PROCESS_VIEW_PATH.is_file(), "docs/PROCESS_VIEW.html is missing")


class ExtractedAllowlistRegexTest(unittest.TestCase):
    """Extracts the real MD_PATH_ALLOWLIST_RE from the shipped file and
    tests it directly, so a typo in the source is caught here."""

    @classmethod
    def setUpClass(cls):
        cls.source = _read(VIEWER_PATH)
        m = re.search(
            r"MD_PATH_ALLOWLIST_RE\s*=\s*/(\^.*\$)/;",
            cls.source,
        )
        assert m, "could not find MD_PATH_ALLOWLIST_RE in DOCS_VIEWER.html"
        js_pattern = m.group(1)
        # The pattern only uses ASCII character classes that are valid in
        # both JS and Python regex syntax, so it can be compiled as-is.
        cls.allowlist_re = re.compile(js_pattern)

    def test_accepts_simple_relative_md(self):
        for good in [
            "PROCESS.md",
            "verification/I02_CORE_BUILD_REPORT_LUNA.md",
            "decisions/0005-mvp-simple-single-verifier.md",
            "a/b/c/deep_file-name.md",
        ]:
            with self.subTest(good=good):
                self.assertTrue(self.allowlist_re.match(good), good)

    def test_rejects_non_md_and_dangerous_chars(self):
        # Note: this allowlist regex is only one of several layered guards
        # in isSafeDocPath() — it is responsible for the character set and
        # the ".md" extension. ".." traversal is rejected by a separate
        # explicit indexOf("..") guard (see PathSafetyReferenceImplementationTest),
        # so it is intentionally not part of this regex-only table.
        for bad in [
            "PROCESS.txt",
            "PROCESS.md.exe",
            "..md",
            "a b.md",
            "a\tb.md",
            "verif*cation/x.md",
            "",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(bool(self.allowlist_re.match(bad)), bad)


class PathSafetyReferenceImplementationTest(unittest.TestCase):
    """Native Python re-implementation of isSafeDocPath(), mirroring the
    guard clauses in DOCS_VIEWER.html one-for-one, run against a large
    table of attack and legitimate inputs."""

    @classmethod
    def setUpClass(cls):
        cls.source = _read(VIEWER_PATH)

    def setUp(self):
        # Verify each guard clause literally exists in the shipped source
        # before trusting the reference implementation mirrors it.
        required_fragments = [
            'raw.indexOf(" ")',
            'raw.indexOf("..")',
            'raw.indexOf("\\\\")',
            'raw.indexOf(":")',
            'raw.charAt(0) === "/"',
            'raw.indexOf("//")',
            "MD_PATH_ALLOWLIST_RE.test(raw)",
        ]
        for frag in required_fragments:
            self.assertIn(frag, self.source, f"missing guard clause: {frag}")

    @staticmethod
    def is_safe_doc_path(raw):
        if not isinstance(raw, str):
            return False
        if len(raw) == 0 or len(raw) > 260:
            return False
        if " " in raw:
            return False
        if ".." in raw:
            return False
        if "\\" in raw:
            return False
        if ":" in raw:
            return False
        if raw.startswith("/"):
            return False
        if "//" in raw:
            return False
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*\.md$", raw):
            return False
        return True

    def test_legitimate_paths_accepted(self):
        for good in [
            "PROCESS.md",
            "IMPLEMENTATION_PLAN.md",
            "verification/I02_CORE_BUILD_REPORT_LUNA.md",
            "architecture/GRAPHORI_ARCHITECTURE.md",
            "decisions/0001-portable-core-orca-adapter.md",
            "evidence/doctori/PROCESS.md",
        ]:
            with self.subTest(good=good):
                self.assertTrue(self.is_safe_doc_path(good), good)

    def test_parent_traversal_rejected(self):
        for bad in [
            "../PROCESS.md",
            "../../etc/passwd.md",
            "verification/../../../secret.md",
            "..%2f..%2fsecret.md".replace("%2f", "/"),  # already-decoded form
            "a/../../b.md",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), bad)

    def test_absolute_paths_rejected(self):
        for bad in [
            "/etc/passwd.md",
            "/PROCESS.md",
            "//PROCESS.md",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), bad)

    def test_windows_drive_and_backslash_rejected(self):
        for bad in [
            "C:\\Windows\\system.ini",
            "C:/Windows/system.ini",
            "..\\..\\secret.md",
            "verification\\I02.md",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), bad)

    def test_url_schemes_rejected(self):
        for bad in [
            "file:///etc/passwd",
            "http://evil.example/x.md",
            "https://evil.example/x.md",
            "javascript:alert(1)",
            "data:text/html,<script>1</script>",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), bad)

    def test_empty_and_missing_rejected(self):
        for bad in ["", None, 123, [], {}]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), repr(bad))

    def test_non_md_extension_rejected(self):
        for bad in ["PROCESS.markdown", "PROCESS", "PROCESS.md.bak", "PROCESS.MD"]:
            with self.subTest(bad=bad):
                self.assertFalse(self.is_safe_doc_path(bad), bad)


class CssRenderContractTest(unittest.TestCase):
    """Assert the readability contract: explicit white background, dark
    (#172033-class) text, styling for code/table/link/heading/list, long
    line wrapping, and UTF-8 charset."""

    @classmethod
    def setUpClass(cls):
        cls.source = _read(VIEWER_PATH)

    def test_utf8_charset_declared(self):
        self.assertRegex(self.source, r'<meta\s+charset=["\']utf-8["\']', "missing UTF-8 charset meta tag")

    def test_color_scheme_forced_light(self):
        self.assertIn("color-scheme: light", self.source)

    def test_explicit_white_background(self):
        self.assertRegex(self.source, r"background:\s*#fff(?:fff)?\b")

    def test_explicit_dark_text_color(self):
        # #172033 must appear as the body/main text color, giving >7:1
        # contrast against a #ffffff background (WCAG AAA for normal text).
        self.assertIn("#172033", self.source)

    def test_element_styles_present(self):
        required_selectors = ["code", "pre", "table", "th,", "a {", "h1,", "ul,", "blockquote"]
        for sel in required_selectors:
            with self.subTest(selector=sel):
                self.assertIn(sel, self.source)

    def test_long_line_wrapping_present(self):
        self.assertIn("overflow-wrap", self.source)
        self.assertIn("white-space: pre-wrap", self.source)

    def test_no_external_network_dependency(self):
        # Must not depend on a CDN/remote font/script — this needs to work
        # opened straight from disk with no network access. (Mentioning
        # "http://" inside the user-facing rejection message is fine; only
        # actual resource-loading tags are disallowed.)
        self.assertNotIn("<script src=", self.source)
        self.assertNotIn("<link ", self.source)
        self.assertNotIn("@import", self.source)
        self.assertNotIn("fonts.googleapis", self.source)

    def test_html_escaping_applied_before_markup(self):
        self.assertIn("function escapeHtml(s)", self.source)
        self.assertIn("s.replace(/&/g,", self.source)

    def test_link_scheme_allowlist_present(self):
        self.assertIn("isSafeHref", self.source)
        self.assertIn('scheme === "http"', self.source)
        self.assertIn('scheme === "mailto"', self.source)


class ProcessViewReusesSharedViewerTest(unittest.TestCase):
    """PROCESS_VIEW.html must not re-implement its own Markdown renderer;
    it must delegate to DOCS_VIEWER.html so there is exactly one renderer
    in the repo."""

    @classmethod
    def setUpClass(cls):
        cls.source = _read(PROCESS_VIEW_PATH)

    def test_redirects_to_shared_viewer_with_process_md(self):
        self.assertIn("DOCS_VIEWER.html?file=PROCESS.md", self.source)

    def test_has_no_duplicate_render_function(self):
        self.assertNotIn("function render(", self.source)
        self.assertNotIn("MD_PATH_ALLOWLIST_RE", self.source)


class NoInlineColorHtmlInMarkdownTest(unittest.TestCase):
    """The readability bug must be fixed in the viewer, never by injecting
    color/style HTML into the tracked Markdown source files."""

    # Patterns are scoped to actual HTML tags (require a preceding "<tag ")
    # so plain-English/pseudocode uses of the word "style" (e.g. a design
    # doc's "style=adversarial" parameter) are not flagged.
    FORBIDDEN_PATTERNS = [
        re.compile(r"<\w+[^>]*\bstyle\s*=", re.IGNORECASE),
        re.compile(r"<font\b", re.IGNORECASE),
        re.compile(r"<span[^>]*\bcolor\b", re.IGNORECASE),
    ]

    def test_docs_markdown_files_have_no_inline_color_html(self):
        md_files = sorted(DOCS_DIR.rglob("*.md"))
        self.assertTrue(md_files, "expected at least one docs/**/*.md file")
        offenders = []
        for path in md_files:
            text = path.read_text(encoding="utf-8")
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    offenders.append((str(path.relative_to(REPO_ROOT)), pattern.pattern))
        self.assertEqual(offenders, [], f"inline color/style HTML found: {offenders}")


if __name__ == "__main__":
    unittest.main()
