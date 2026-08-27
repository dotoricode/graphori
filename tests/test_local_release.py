import json
import unittest
from pathlib import Path


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

    def test_readmes_split_codex_and_claude_skill_installation(self):
        for name in ("README.md", "README.ko.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                self.assertIn("npx skills add dotoricode/graphori --list", text)
                self.assertIn("--skill graphori --agent codex --copy", text)
                self.assertIn("--skill graphori --agent claude-code --copy", text)
                self.assertNotIn("--agent codex --global", text)
                self.assertIn("codex plugin marketplace add dotoricode/graphori", text)
                self.assertIn("codex plugin add graphori@graphori", text)
                self.assertIn("/plugin marketplace add dotoricode/graphori", text)
                self.assertIn("/plugin install graphori@graphori", text)
                self.assertIn("gh repo clone dotoricode/graphori -- --depth 1", text)
                self.assertIn("### Codex", text)
                self.assertIn("### Claude Code", text)
                self.assertIn("--mode solo --target codex", text)
                self.assertIn("--target claude", text)
                self.assertIn("~/.agents/skills/graphori", text)
                self.assertIn("~/.claude/skills/graphori", text)
                self.assertIn("$graphori", text)
                self.assertIn("/graphori", text)

                self.assertLess(
                    text.index("codex plugin marketplace add dotoricode/graphori"),
                    text.index("npx skills add dotoricode/graphori --list"),
                )
                self.assertLess(
                    text.index("npx skills add dotoricode/graphori --list"),
                    text.index("gh repo clone dotoricode/graphori -- --depth 1"),
                )


if __name__ == "__main__":
    unittest.main()
