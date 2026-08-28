"""Run-root confined path resolution.

Every journal/evidence write goes through :func:`safe_join`, which rejects
traversal, absolute/drive-relative/UNC escapes, symlink/junction escapes
(caught by realpath resolution, which Windows resolves reparse points for
since Python 3.8), and case-collision ambiguity on case-insensitive
filesystems.  Nothing in this module trusts a caller-supplied filename to be
safe on its own.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


class PathSecurityError(ValueError):
    """Raised when a path would escape or collide outside the run root."""


_SEPARATORS = re.compile(r"[\\/]+")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def resolve_run_root(root: os.PathLike | str) -> Path:
    """Resolve ``root`` to an absolute, symlink/junction-free real path."""
    candidate = Path(root)
    if not candidate.is_absolute():
        raise PathSecurityError(f"run root must be an absolute path: {root!r}")
    return Path(os.path.realpath(str(candidate)))


def _reject_component(piece: str) -> None:
    if piece in ("", ".", ".."):
        raise PathSecurityError(f"invalid path component: {piece!r}")
    if ":" in piece:
        raise PathSecurityError(f"path component must not contain a drive marker: {piece!r}")


def _reject_escaping_segment(part: str) -> None:
    if part.startswith("\\\\") or part.startswith("//"):
        raise PathSecurityError(f"UNC path segment is not allowed: {part!r}")
    if _DRIVE_PREFIX.match(part):
        raise PathSecurityError(f"drive-relative path segment is not allowed: {part!r}")
    if Path(part).is_absolute():
        raise PathSecurityError(f"absolute path segment is not allowed: {part!r}")


def _check_case_collision(candidate: Path) -> None:
    parent = candidate.parent
    if not parent.is_dir():
        return
    target = candidate.name
    try:
        entries = os.listdir(parent)
    except OSError:
        return
    for entry in entries:
        if entry != target and entry.casefold() == target.casefold():
            raise PathSecurityError(
                f"case-collision ambiguity between {entry!r} and {target!r} in {parent}"
            )


def safe_join(root: os.PathLike | str, *relative_parts: str) -> Path:
    """Join ``relative_parts`` onto ``root`` and confine the result to it.

    ``root`` may already be a resolved :class:`Path` (e.g. from a prior
    :func:`resolve_run_root` call) or a raw path to resolve now.
    """
    resolved_root = root if isinstance(root, Path) and root.is_absolute() else resolve_run_root(root)

    candidate = resolved_root
    for part in relative_parts:
        text = str(part)
        _reject_escaping_segment(text)
        for piece in _SEPARATORS.split(text):
            if piece == "":
                continue
            _reject_component(piece)
            candidate = candidate / piece
            _check_case_collision(candidate)

    real = Path(os.path.realpath(str(candidate)))
    try:
        real.relative_to(resolved_root)
    except ValueError:
        raise PathSecurityError(f"resolved path escapes run root: {real} not under {resolved_root}") from None
    return candidate
