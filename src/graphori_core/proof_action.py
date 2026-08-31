"""Stable identity for Graphori-observable verifier execution inputs.

ProofActionKey v0 deliberately covers the execution envelope that Graphori can
observe or that a caller explicitly declares.  It does not claim to identify
the complete transitive toolchain or every library and configuration file an
interpreter, build tool, or wrapper may read.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from .process_supervisor import (
    DEFAULT_ENV_ALLOWLIST,
    build_child_env,
    resolve_workspace_path,
)


ACTION_KEY_SCHEMA = "graphori-proof-action-v0"
REUSABLE = "REUSABLE"
INCOMPLETE = "INCOMPLETE"


def _digest_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8", "surrogateescape")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _entry_executable(argv0: str, *, cwd: Path,
                      child_env: Mapping[str, str]) -> Path | None:
    candidate = Path(argv0)
    if candidate.is_absolute():
        resolved = candidate
    elif any(separator in argv0 for separator in ("/", "\\")):
        resolved = cwd / candidate
    else:
        found = shutil.which(argv0, path=child_env.get("PATH"))
        if found is None:
            return None
        resolved = Path(found)
    try:
        resolved = resolved.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_file() else None


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class EntryExecutableIdentity:
    """Identity of the entry file directly executed by ProcessSupervisor.

    This is intentionally not named or treated as a full toolchain identity.
    The persisted form contains only a basename and content digest, not a host
    path that may expose a user's directory layout.
    """

    basename: str
    content_digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "basename": self.basename,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class ProofActionKey:
    """Canonical, secret-safe description of one observable proof action."""

    proof_ids: tuple[str, ...]
    argv: tuple[str, ...]
    cwd: str
    input_digest: str
    env_names: tuple[str, ...]
    env_digest: str
    entry_executable_identity: EntryExecutableIdentity | None
    permission_profile: str
    sandbox_profile: str
    network_policy: str
    verifier_identity: str
    eligibility: str
    incomplete_reasons: tuple[str, ...] = ()
    schema: str = ACTION_KEY_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        """Return the only representation safe to persist or log.

        Raw environment values and per-variable value hashes are never held by
        this object, so callers cannot accidentally serialize them.
        """

        return {
            "schema": self.schema,
            "proof_ids": list(self.proof_ids),
            "argv": list(self.argv),
            "cwd": self.cwd,
            "input_digest": self.input_digest,
            "env_names": list(self.env_names),
            "env_digest": self.env_digest,
            "entry_executable_identity": (
                self.entry_executable_identity.to_dict()
                if self.entry_executable_identity is not None else None
            ),
            "permission_profile": self.permission_profile,
            "sandbox_profile": self.sandbox_profile,
            "network_policy": self.network_policy,
            "verifier_identity": self.verifier_identity,
            "eligibility": self.eligibility,
            "incomplete_reasons": list(self.incomplete_reasons),
        }

    def digest(self) -> str:
        return _digest_json(self.to_dict())


def build_proof_action_key(
        *, workspace_root: os.PathLike[str] | str, proof_ids: Sequence[str],
        argv: Sequence[str], cwd: str, input_digest: str,
        env: Mapping[str, str] | None = None,
        env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
        permission_profile: str, sandbox_profile: str, network_policy: str,
        verifier_identity: str,
        base_env: Mapping[str, str] | None = None) -> ProofActionKey:
    """Build a v0 key from the same filtered environment used by the child.

    The complete filtered environment contributes to one aggregate digest.
    Only its sorted names and that aggregate digest survive this function.
    """

    normalized_argv = tuple(argv)
    normalized_proofs = tuple(sorted(set(proof_ids)))
    reasons: list[str] = []
    if not normalized_argv or any(not isinstance(item, str) or not item
                                  for item in normalized_argv):
        reasons.append("invalid_argv")
    if not normalized_proofs:
        reasons.append("missing_proof_identity")
    for name, value in (
        ("input_digest", input_digest),
        ("permission_profile", permission_profile),
        ("sandbox_profile", sandbox_profile),
        ("network_policy", network_policy),
        ("verifier_identity", verifier_identity),
    ):
        if not value:
            reasons.append(f"missing_{name}")

    child_env, _dropped = build_child_env(
        base_env=os.environ if base_env is None else base_env,
        extra_env=env,
        allowlist=env_allowlist,
    )
    env_items = sorted(child_env.items())
    env_names = tuple(name for name, _value in env_items)
    env_digest = _digest_json(env_items)

    normalized_cwd = cwd
    entry_identity: EntryExecutableIdentity | None = None
    try:
        resolved_root = Path(workspace_root).resolve()
        resolved_cwd = resolve_workspace_path(resolved_root, cwd)
        normalized_cwd = resolved_cwd.relative_to(resolved_root).as_posix() or "."
        if normalized_argv:
            executable = _entry_executable(
                normalized_argv[0], cwd=resolved_cwd, child_env=child_env,
            )
            if executable is None:
                reasons.append("entry_executable_unavailable")
            else:
                entry_identity = EntryExecutableIdentity(
                    executable.name, _file_digest(executable),
                )
    except (OSError, ValueError):
        reasons.append("execution_envelope_unavailable")

    normalized_reasons = tuple(sorted(set(reasons)))
    return ProofActionKey(
        proof_ids=normalized_proofs,
        argv=normalized_argv,
        cwd=normalized_cwd,
        input_digest=input_digest,
        env_names=env_names,
        env_digest=env_digest,
        entry_executable_identity=entry_identity,
        permission_profile=permission_profile,
        sandbox_profile=sandbox_profile,
        network_policy=network_policy,
        verifier_identity=verifier_identity,
        eligibility=INCOMPLETE if normalized_reasons else REUSABLE,
        incomplete_reasons=normalized_reasons,
    )
