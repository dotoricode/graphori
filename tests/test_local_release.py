import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LocalReleaseContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
