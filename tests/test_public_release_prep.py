from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "scripts" / "export_public_tree.py"
AUDITOR = ROOT / "scripts" / "public_release_audit.py"


def run(*args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class PublicTreeExportTests(unittest.TestCase):
    def make_repository(self, parent: Path) -> Path:
        root = parent / "private-source"
        root.mkdir()
        self.assertEqual(run("git", "init", "-q", cwd=root).returncode, 0)
        (root / "README.md").write_text("# Reviewed tree\n", encoding="utf-8")
        (root / "untracked.txt").write_text("included\n", encoding="utf-8")
        (root / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        self.assertEqual(
            run("git", "add", "README.md", ".gitignore", cwd=root).returncode,
            0,
        )
        return root

    def test_dry_run_does_not_create_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.make_repository(parent)
            destination = parent / "public-export"

            result = run(
                sys.executable,
                EXPORTER,
                destination,
                "--root",
                root,
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(destination.exists())
            self.assertIn("PUBLIC TREE DRY RUN", result.stdout)

    def test_export_has_no_history_and_manifest_matches_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.make_repository(parent)
            destination = parent / "public-export"

            result = run(
                sys.executable,
                EXPORTER,
                destination,
                "--root",
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((destination / "README.md").is_file())
            self.assertTrue((destination / "untracked.txt").is_file())
            self.assertFalse((destination / "ignored.txt").exists())
            self.assertFalse((destination / ".git").exists())
            manifest = json.loads(
                (destination / "PUBLIC_TREE_MANIFEST.json").read_text(encoding="utf-8")
            )
            expected = hashlib.sha256(
                (destination / "README.md").read_bytes()
            ).hexdigest()
            files = {item["path"]: item["sha256"] for item in manifest["files"]}
            self.assertEqual(files["README.md"], expected)

            repeated = run(
                sys.executable,
                EXPORTER,
                destination,
                "--root",
                root,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("destination already exists", repeated.stderr)

    def test_export_omits_tracked_files_deleted_from_working_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.make_repository(parent)
            removed = root / "removed.txt"
            removed.write_text("old workflow\n", encoding="utf-8")
            self.assertEqual(run("git", "add", "removed.txt", cwd=root).returncode, 0)
            removed.unlink()
            destination = parent / "public-export"

            result = run(
                sys.executable,
                EXPORTER,
                destination,
                "--root",
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((destination / "removed.txt").exists())
            manifest = json.loads(
                (destination / "PUBLIC_TREE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("removed.txt", {item["path"] for item in manifest["files"]})


class PublicTreeAuditTests(unittest.TestCase):
    @staticmethod
    def write_required(root: Path) -> None:
        required = (
            "LICENSE",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "THIRD_PARTY_NOTICES.md",
            "README.md",
            "README.ko.md",
            "benchmarks/raw-result.schema.json",
            "scripts/export_public_tree.py",
            "scripts/public_release_audit.py",
            "scripts/verify_public_release.py",
        )
        for relative in required:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("reviewed\n", encoding="utf-8")

    def test_tree_only_audit_accepts_required_reviewed_files_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_required(root)

            result = run(
                sys.executable,
                AUDITOR,
                "--root",
                root,
                "--tree-only",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("tree checks passed", result.stdout)

    def test_tree_only_audit_fails_closed_on_missing_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run(
                sys.executable,
                AUDITOR,
                "--root",
                temporary,
                "--tree-only",
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("NOT READY", result.stderr)
            self.assertIn("missing required control", result.stderr)

    def test_tree_only_audit_rejects_the_current_home_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_required(root)
            (root / "private-note.txt").write_text(
                f"local checkout: {Path.home() / 'project'}\n",
                encoding="utf-8",
            )

            result = run(
                sys.executable,
                AUDITOR,
                "--root",
                root,
                "--tree-only",
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("private path or organization identifier", result.stderr)

    def initialize_history(self, root: Path) -> None:
        self.assertEqual(run("git", "init", "-q", "-b", "main", cwd=root).returncode, 0)
        self.assertEqual(
            run("git", "config", "user.name", "Release Test", cwd=root).returncode,
            0,
        )
        self.assertEqual(
            run(
                "git",
                "config",
                "user.email",
                "release-test@users.noreply.github.com",
                cwd=root,
            ).returncode,
            0,
        )

    def commit_all(self, root: Path, message: str) -> None:
        self.assertEqual(run("git", "add", ".", cwd=root).returncode, 0)
        result = run("git", "commit", "-q", "-m", message, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_audit_accepts_one_clean_noreply_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_required(root)
            self.initialize_history(root)
            self.commit_all(root, "clean release")

            result = run(sys.executable, AUDITOR, "--root", root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("tree and history checks passed", result.stdout)

    def test_full_audit_finds_private_path_removed_from_current_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_required(root)
            self.initialize_history(root)
            note = root / "old-note.md"
            note.write_text("checkout: /Users/private-person/project\n", encoding="utf-8")
            self.commit_all(root, "private history")
            note.write_text("reviewed\n", encoding="utf-8")
            self.commit_all(root, "sanitize current tree")

            result = run(sys.executable, AUDITOR, "--root", root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("git history contains personal path", result.stderr)


if __name__ == "__main__":
    unittest.main()
