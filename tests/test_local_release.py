import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.verify_public_release import is_git_repository


ROOT = Path(__file__).parents[1]


class LocalReleaseContractTests(unittest.TestCase):
    def test_native_plugin_manifests_share_one_identity_and_skill_sources(self):
        codex = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex_marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        claude_marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(codex["name"], "graphori")
        self.assertEqual(claude["name"], codex["name"])
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual(codex["skills"], "./skills/")
        self.assertEqual(claude["skills"], "./skills/")
        self.assertEqual(codex_marketplace["name"], "graphori")
        self.assertEqual(claude_marketplace["name"], "graphori")
        self.assertEqual(
            codex_marketplace["plugins"][0]["policy"],
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        )

    def test_repository_has_no_github_actions_workflows(self):
        workflows = ROOT / ".github" / "workflows"
        found = [] if not workflows.exists() else [
            path for path in workflows.iterdir()
            if path.suffix.lower() in {".yml", ".yaml"}
        ]
        self.assertEqual(found, [])

    def test_local_release_verifier_covers_required_boundaries(self):
        text = (ROOT / "scripts" / "verify_public_release.py").read_text(encoding="utf-8")
        for token in (
            "unittest", "compileall", "validate_docs_indexes.py",
            "validate_skill.py", "dashboard_smoke.py", "public_release_audit.py",
            "gitleaks", "pip-audit", "twine", "SHA256SUMS",
        ):
            self.assertIn(token, text)

    def test_release_verifier_accepts_a_linked_git_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            linked = root / "linked"
            source.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Release Test",
                 "-c", "user.email=release-test@users.noreply.github.com",
                 "commit", "--allow-empty", "-qm", "test"],
                cwd=source, check=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-q", str(linked)],
                cwd=source, check=True,
            )

            self.assertTrue((linked / ".git").is_file())
            self.assertTrue(is_git_repository(linked))
            nested = linked / "nested"
            nested.mkdir()
            self.assertFalse(is_git_repository(nested))

    def test_readmes_split_codex_and_claude_skill_installation(self):
        """Each language documents both agents across its install document set.

        The README carries the native plugin install for both agents; the
        shared INSTALL.md carries the preview, copy, and clone routes. A token
        satisfies the contract when it appears anywhere in that set.
        """
        shared = (ROOT / "docs" / "public" / "INSTALL.md").read_text(encoding="utf-8")
        for name in ("README.md", "README.ko.md"):
            readme = (ROOT / name).read_text(encoding="utf-8")
            combined = readme + chr(10) + shared
            with self.subTest(readme=name):
                # Both agents get a native plugin install in the README itself.
                self.assertIn("codex plugin marketplace add dotoricode/graphori", readme)
                self.assertIn("codex plugin add graphori@graphori", readme)
                self.assertIn("/plugin marketplace add dotoricode/graphori", readme)
                self.assertIn("/plugin install graphori@graphori", readme)
                self.assertIn("### Codex", readme)
                self.assertIn("### Claude Code", readme)
                # The remaining routes may live in the shared install document.
                self.assertIn("npx skills add dotoricode/graphori --list", combined)
                self.assertIn("--skill graphori --agent codex --copy", combined)
                self.assertIn("--skill graphori --agent claude-code --copy", combined)
                self.assertIn("gh repo clone dotoricode/graphori -- --depth 1", combined)
                self.assertIn("--mode solo --target codex", combined)
                self.assertIn("--target claude", combined)
                self.assertIn("~/.agents/skills/graphori", combined)
                self.assertIn("~/.claude/skills/graphori", combined)
                # The CLI's global Codex path is wrong; never document it.
                self.assertNotIn("--agent codex --global", combined)
                self.assertIn("$graphori", readme)
                self.assertIn("/graphori", readme)
                # Routes stay ordered from least to most manual: the native
                # plugin install in the README, then preview, then clone.
                self.assertLess(
                    shared.index("npx skills add dotoricode/graphori --list"),
                    shared.index("gh repo clone dotoricode/graphori -- --depth 1"),
                )

    def test_readmes_publish_the_complete_small_benchmark_boundary(self):
        required = (
            "567,584", "333,681", "396,800", "267,776", "170,784",
            "65,905", "4,960", "3,309", "48.5", "32.1", "72",
        )
        for name in ("README.md", "README.ko.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                for value in required:
                    self.assertIn(value, text)
                self.assertIn("not recorded" if name == "README.md" else "기록 안 됨", text)
                self.assertIn("has not run" if name == "README.md" else "아직 실행하지", text)


if __name__ == "__main__":
    unittest.main()
