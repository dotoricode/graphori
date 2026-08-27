#!/usr/bin/env python3
"""Check that every markdown-bearing directory has a Korean README index."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

NUL = chr(0)


def excluded(path: Path) -> bool:
    return (bool(path.parts) and (path.parts[0].lower() in {"graphori", "skills"}
                                  or any(part.startswith(".") for part in path.parts)))


def tracked_markdown(root: Path) -> list[Path]:
    """Markdown files Git actually tracks.

    Walking the filesystem would also pick up build output and other ignored
    directories, which are not part of the published tree and have no index.
    """
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "*.md"],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        return sorted(root.rglob("*.md"))
    return [root / name for name in completed.stdout.split(NUL) if name]


def expected(root: Path) -> dict[Path, list[str]]:
    result: dict[Path, list[str]] = {}
    for path in tracked_markdown(root):
        relative = path.relative_to(root)
        if excluded(relative) or path.name.lower() == "readme.md":
            continue
        result.setdefault(path.parent, []).append(path.name)
    return result


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for directory, names in expected(root).items():
        readme = directory / "README.md"
        if not readme.is_file():
            errors.append(f"missing index: {readme.relative_to(root)}")
            continue
        text = readme.read_text(encoding="utf-8")
        for name in sorted(names):
            if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text):
                errors.append(f"{readme.relative_to(root)} does not index {name}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = validate(root)
    if errors:
        print("Document indexes are invalid:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    count = sum(len(names) for names in expected(root).values())
    print(f"Document indexes are valid ({count} markdown documents indexed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
