"""Private, single-workspace storage for resumable provider capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import secrets


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

    def _directory(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("run ID is not safe for private session storage")
        return self.workspace / ".graphori" / "runs" / run_id / "private" / "sessions"

    def put(self, run_id: str, binding: PrivateSessionBinding) -> str:
        directory = self._directory(run_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        for _ in range(8):
            token = secrets.token_hex(16)
            target = directory / f"{token}.json"
            try:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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
            return token
        raise RuntimeError("could not allocate a private session handle")

    def resolve(
            self, run_id: str, token: str, *, provider: str,
            boundary_digest: str, attempt_id: str) -> PrivateSessionBinding | None:
        if not _SAFE_TOKEN.fullmatch(token):
            return None
        target = self._directory(run_id) / f"{token}.json"
        try:
            stat = target.stat()
            if stat.st_mode & 0o077:
                return None
            value = json.loads(target.read_text(encoding="utf-8"))
            binding = PrivateSessionBinding(**value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if (
                binding.provider != provider
                or binding.boundary_digest != boundary_digest
                or binding.attempt_id != attempt_id):
            return None
        return binding

    def clear_run(self, run_id: str) -> None:
        directory = self._directory(run_id)
        if not directory.is_dir():
            return
        for target in directory.iterdir():
            if target.is_file() and _SAFE_TOKEN.fullmatch(target.stem):
                target.unlink(missing_ok=True)
        try:
            directory.rmdir()
            directory.parent.rmdir()
        except OSError:
            pass
