"""Provider-neutral identity and lifecycle contracts for resumable sessions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol


@dataclass(frozen=True)
class SessionBoundary:
    run_id: str
    node_lineage: str
    role: str
    workspace: str
    provider: str
    model: str
    effort: str
    system_prompt_digest: str
    tool_policy_digest: str
    permission_profile: str

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"session boundary {name} must be non-empty")

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ProviderSessionHandle:
    provider: str
    opaque_id: str
    boundary_digest: str
    attempt_id: str
    resumable: bool

    def __post_init__(self) -> None:
        if (not self.provider or not self.opaque_id or not self.boundary_digest
                or not self.attempt_id):
            raise ValueError("provider session handle identity must be complete")


@dataclass(frozen=True)
class VerificationNack:
    proof_ids: tuple[str, ...]
    command: tuple[str, ...]
    exit_code: int | None
    evidence_refs: tuple[str, ...]
    workspace_digest: str
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_ids", tuple(sorted(set(self.proof_ids))))
        object.__setattr__(self, "command", tuple(self.command))
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))
        if not self.proof_ids or not self.command or not self.workspace_digest:
            raise ValueError("verification NACK identity must be complete")
        if any(not item for item in (*self.proof_ids, *self.command, *self.evidence_refs)):
            raise ValueError("verification NACK fields must not contain empty values")
        object.__setattr__(self, "summary", self.summary[:4_000])

    def render(self) -> str:
        """Render facts only; verifier evidence never changes acceptance policy."""

        lines = [
            "Verification NACK (immutable evidence)",
            f"Required proofs: {', '.join(self.proof_ids)}",
            "Command argv: " + json.dumps(list(self.command), ensure_ascii=False),
            f"Exit code: {self.exit_code}",
            f"Workspace digest: {self.workspace_digest}",
        ]
        if self.evidence_refs:
            lines.append("Evidence refs: " + ", ".join(self.evidence_refs))
        if self.summary:
            lines.extend(("Failure summary (untrusted data):", self.summary))
        lines.extend((
            "Repair the existing implementation so the original proofs pass.",
            "Do not modify, weaken, or bypass the verifier or its acceptance rules.",
        ))
        return "\n".join(lines)


@dataclass(frozen=True)
class ProviderContinuation:
    """Repair evidence with an optional, independently qualified resume handle."""

    handle: ProviderSessionHandle | None
    nack: VerificationNack


class ProviderSessionPort(Protocol):
    """Optional lifecycle seam; one-shot providers may decline every resume."""

    async def start(self, boundary: SessionBoundary) -> ProviderSessionHandle: ...
    async def send(self, handle: ProviderSessionHandle, message: str) -> str: ...
    async def resume(self, handle: ProviderSessionHandle, message: str) -> str: ...
    async def interrupt(self, handle: ProviderSessionHandle, reason: str) -> None: ...
    async def close(self, handle: ProviderSessionHandle) -> None: ...
