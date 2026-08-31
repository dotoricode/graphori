"""Deterministic identity for the verifier-visible workspace."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil


_EXCLUDED_DIRECTORIES = {".git", ".graphori", "__pycache__"}


def workspace_files(root: Path) -> tuple[Path, ...]:
    values: list[Path] = []
    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in _EXCLUDED_DIRECTORIES)
        base = Path(directory)
        if any((base / name).is_symlink() for name in names):
            raise ValueError("workspace snapshot does not support directory symlinks")
        values.extend((base / name).relative_to(root) for name in sorted(files))
    return tuple(sorted(values, key=lambda item: item.as_posix()))


def workspace_digest(root: Path) -> str:
    """Hash workspace inputs while excluding Graphori's own runtime state."""

    digest = hashlib.sha256()
    for relative_path in workspace_files(root):
        path = root / relative_path
        if path.is_symlink():
            raise ValueError("workspace snapshot does not support file symlinks")
        if not path.is_file():
            if path.exists():
                raise ValueError("workspace snapshot does not support special files")
            continue
        relative = relative_path.as_posix().encode("utf-8", "surrogateescape")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def copy_workspace(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for relative in workspace_files(root):
        source = root / relative
        if source.is_symlink():
            raise ValueError("workspace snapshot does not support symlinks")
        if not source.is_file():
            if source.exists():
                raise ValueError("workspace snapshot does not support special files")
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
