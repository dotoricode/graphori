#!/usr/bin/env python3
"""Export the reviewed working tree without copying the private Git history."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


def listed_files(root: Path) -> list[PurePosixPath]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    paths: list[PurePosixPath] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        value = raw.decode("utf-8")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe repository path: {value}")
        paths.append(path)
    return sorted(set(paths), key=str)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(root: Path, destination: Path, *, dry_run: bool) -> int:
    root = root.resolve()
    destination = destination.resolve()
    if destination == root or root in destination.parents:
        raise ValueError("destination must be outside the private repository")
    if destination.exists():
        raise ValueError("destination already exists; refusing to merge or overwrite")

    listed = listed_files(root)
    paths: list[PurePosixPath] = []
    for relative in listed:
        source = root.joinpath(*relative.parts)
        if not source.exists():
            continue
        if source.is_symlink():
            raise ValueError(f"symbolic links are not exported: {relative}")
        if not source.is_file():
            raise ValueError(f"listed path is not a regular file: {relative}")
        paths.append(relative)
    if dry_run:
        print(f"PUBLIC TREE DRY RUN: {len(paths)} files -> {destination}")
        return 0

    destination.mkdir(parents=True)
    manifest: list[dict[str, str]] = []
    for relative in paths:
        source = root.joinpath(*relative.parts)
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({"path": str(relative), "sha256": file_digest(target)})
    (destination / "PUBLIC_TREE_MANIFEST.json").write_text(
        json.dumps(
            {"schema_version": 1, "files": manifest},
            indent=2, sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"PUBLIC TREE EXPORTED: {len(paths)} files -> {destination}")
    print("No Git repository, commit, remote, or visibility change was created.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        return export(args.root, args.destination, dry_run=args.dry_run)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
