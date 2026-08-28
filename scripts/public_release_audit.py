#!/usr/bin/env python3
"""Fail closed on missing public-beta controls; never publish or rewrite history."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    "THIRD_PARTY_NOTICES.md", "README.md", "README.ko.md",
    ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json",
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
    "benchmarks/raw-result.schema.json",
    "scripts/export_public_tree.py", "scripts/public_release_audit.py",
    "scripts/verify_public_release.py",
)
SECRET = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{12,}"
)
PRIVATE_HISTORY = re.compile(
    r"(?i)(?:/Users/|[A-Z]:\\Users\\|youngsang(?:[._-]?kwon)?|everspin|eversafe|fakefinder)"
)
PRIVATE_HISTORY_GREP = r"(/Users/|[A-Z]:\\Users\\|youngsang|everspin|eversafe|fakefinder)"
PRIVATE_TREE_MARKERS = (
    str(Path.home()),
    "ever" + "spin",
    "ever" + "safe",
    "fake" + "finder",
)
SKIPPED_SUFFIXES = {".png", ".webp", ".woff2", ".pyc"}
SKIPPED_PARTS = {".git", ".graphori", "build", "__pycache__"}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.STDOUT,
    )


def history_contains_private_identifiers(root: Path) -> bool:
    revisions = git(root, "rev-list", "--all").splitlines()
    excluded = (
        ":(exclude)scripts/public_release_audit.py",
        ":(exclude)tests/test_personal_paths.py",
        ":(exclude)tests/test_public_release_prep.py",
    )
    for revision in revisions:
        result = subprocess.run(
            [
                "git", "grep", "-I", "-l", "-E", PRIVATE_HISTORY_GREP,
                revision, "--", ".", *excluded,
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr,
            )
        if result.stdout.strip():
            return True
    return False


def audit_tree(root: Path) -> list[str]:
    errors = [
        f"missing required control: {item}"
        for item in REQUIRED if not (root / item).is_file()
    ]
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or any(part in SKIPPED_PARTS for part in path.parts)
            or path.suffix.lower() in SKIPPED_SUFFIXES
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if SECRET.search(text):
                errors.append(
                    f"possible credential-shaped value in current tree: {path.relative_to(root)}"
                )
            relative = path.relative_to(root)
            if (
                relative != Path("scripts/public_release_audit.py")
                and any(marker.casefold() in text.casefold() for marker in PRIVATE_TREE_MARKERS)
            ):
                errors.append(
                    f"private path or organization identifier in current tree: {relative}"
                )
        except UnicodeDecodeError:
            continue
    return errors


def audit_history(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        history = git(root, "log", "--all", "--format=%H", "-n", "1").strip()
        if not history:
            return ["git history is unavailable"]
        history_text = git(
            root, "log", "--all", "-p", "-G",
            r"(api[_-]?key|secret|token|password)[[:space:]]*[:=]",
        )
        if SECRET.search(history_text):
            errors.append("possible committed credential-shaped value found")
        author_emails = {
            item.strip() for item in git(root, "log", "--all", "--format=%ae").splitlines()
            if item.strip() and not item.strip().endswith("@users.noreply.github.com")
        }
        if author_emails:
            errors.append(
                f"git history contains {len(author_emails)} non-noreply author email identity/identities"
            )
        if history_contains_private_identifiers(root):
            errors.append("git history contains personal path or organization-shaped identifiers")
    except (OSError, subprocess.CalledProcessError) as exc:
        if not (isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 1):
            errors.append(f"cannot inspect git history safely: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--tree-only", action="store_true",
        help="audit an exported tree before it has a new Git history",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    errors = audit_tree(root)
    if not args.tree_only:
        errors.extend(audit_history(root))
    if errors:
        print("PUBLIC RELEASE AUDIT: NOT READY", file=sys.stderr)
        print("\n".join(f"- {item}" for item in errors), file=sys.stderr)
        return 1
    boundary = "tree checks" if args.tree_only else "tree and history checks"
    print(f"PUBLIC RELEASE AUDIT: {boundary} passed; no publish/deploy action was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
