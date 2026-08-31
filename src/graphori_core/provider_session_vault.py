"""Private, single-workspace storage for resumable provider capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import secrets
import stat


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_TOKEN = re.compile(r"^[a-f0-9]{32}$")


@dataclass(frozen=True)
class PrivateSessionBinding:
    provider: str
    provider_session_id: str
    boundary_digest: str
    attempt_id: str
    observed_model: str

    def __post_init__(self) -> None:
        values = asdict(self)
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise ValueError("private session binding must be complete")
        if len(self.provider_session_id) > 512 or any(
                ord(character) < 0x20 for character in self.provider_session_id):
            raise ValueError("provider session ID is malformed")


class ProviderSessionVault:
    """Keep raw provider IDs out of the canonical journal and projection."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()

    @staticmethod
    def secure_storage_supported() -> bool:
        required_dir_fd = (os.open, os.mkdir, os.stat, os.unlink)
        return bool(
            getattr(os, "O_NOFOLLOW", 0)
            and getattr(os, "O_DIRECTORY", 0)
            and all(function in os.supports_dir_fd for function in required_dir_fd)
            and os.stat in os.supports_follow_symlinks
        )

    def _directory(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("run ID is not safe for private session storage")
        return self.workspace / ".graphori" / "runs" / run_id / "private" / "sessions"

    def _open_directory(self, run_id: str, *, create: bool) -> int:
        """Open the vault without following any directory-component symlink."""

        self._directory(run_id)  # Validate before using the ID as one component.
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory_flag = getattr(os, "O_DIRECTORY", 0)
        if not self.secure_storage_supported():
            raise OSError("secure private session storage is unavailable")
        current = os.open(self.workspace, os.O_RDONLY | directory_flag | nofollow)
        try:
            for component in (".graphori", "runs", run_id, "private", "sessions"):
                if create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                child = os.open(
                    component,
                    os.O_RDONLY | directory_flag | nofollow,
                    dir_fd=current,
                )
                os.close(current)
                current = child
            os.fchmod(current, 0o700)
            return current
        except BaseException:
            os.close(current)
            raise

    def put(self, run_id: str, binding: PrivateSessionBinding) -> str:
        directory = self._open_directory(run_id, create=True)
        try:
            for _ in range(8):
                token = secrets.token_hex(16)
                try:
                    descriptor = os.open(
                        f"{token}.json",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory,
                    )
                except FileExistsError:
                    continue
                try:
                    payload = json.dumps(
                        asdict(binding), sort_keys=True, separators=(",", ":"),
                    ).encode("utf-8")
                    os.write(descriptor, payload)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.fsync(directory)
                return token
            raise RuntimeError("could not allocate a private session handle")
        finally:
            os.close(directory)

    def resolve(
            self, run_id: str, token: str, *, provider: str,
            boundary_digest: str, attempt_id: str) -> PrivateSessionBinding | None:
        if not _SAFE_TOKEN.fullmatch(token):
            return None
        directory = -1
        descriptor = -1
        try:
            directory = self._open_directory(run_id, create=False)
            descriptor = os.open(
                f"{token}.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory,
            )
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_mode & 0o077:
                return None
            with os.fdopen(os.dup(descriptor), "r", encoding="utf-8") as stream:
                value = json.load(stream)
            binding = PrivateSessionBinding(**value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if directory >= 0:
                os.close(directory)
        if (
                binding.provider != provider
                or binding.boundary_digest != boundary_digest
                or binding.attempt_id != attempt_id):
            return None
        return binding

    def clear_run(self, run_id: str) -> None:
        try:
            directory = self._open_directory(run_id, create=False)
        except OSError:
            return
        try:
            for name in os.listdir(directory):
                if not name.endswith(".json") or not _SAFE_TOKEN.fullmatch(name[:-5]):
                    continue
                try:
                    file_stat = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISREG(file_stat.st_mode):
                        os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    continue
            os.fsync(directory)
        finally:
            os.close(directory)
