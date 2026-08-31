"""Deterministic adoption boundary for speculative proof candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .proof_action import INCOMPLETE, ProofActionKey


@dataclass(frozen=True)
class ProofCandidate:
    """Non-authoritative evidence proposed for later canonical adoption."""

    proof_ids: tuple[str, ...]
    source_digest: str
    action_schema: str
    action_digest: str
    evidence_refs: tuple[str, ...]
    verdict: str
    producer: str = "live-verify"

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_ids", tuple(sorted(set(self.proof_ids))))
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))
        if not self.proof_ids or not self.source_digest:
            raise ValueError("proof candidate identity must be complete")
        if not self.action_schema or not self.action_digest or not self.producer:
            raise ValueError("proof candidate provenance must be complete")
        if self.verdict not in {"pass", "fail"}:
            raise ValueError("proof candidate verdict must be pass or fail")
        if not self.evidence_refs:
            raise ValueError("proof candidate requires evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_digest": self.action_digest,
            "action_schema": self.action_schema,
            "evidence_refs": list(self.evidence_refs),
            "producer": self.producer,
            "proof_ids": list(self.proof_ids),
            "source_digest": self.source_digest,
            "verdict": self.verdict,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ProofAdoptionDecision:
    adopted: bool
    reason: str
    candidate_digest: str


class ProofAdopter:
    """Accept candidates only when current deterministic fences still match."""

    @staticmethod
    def decide(candidate: ProofCandidate, *, current_source_digest: str,
               current_action_key: ProofActionKey) -> ProofAdoptionDecision:
        candidate_digest = candidate.digest()
        if candidate.verdict != "pass":
            return ProofAdoptionDecision(False, "candidate_not_pass", candidate_digest)
        if current_action_key.eligibility == INCOMPLETE:
            return ProofAdoptionDecision(False, "action_key_incomplete", candidate_digest)
        if current_source_digest != candidate.source_digest:
            return ProofAdoptionDecision(False, "source_changed", candidate_digest)
        if current_action_key.schema != candidate.action_schema:
            return ProofAdoptionDecision(False, "action_schema_changed", candidate_digest)
        if current_action_key.digest() != candidate.action_digest:
            return ProofAdoptionDecision(False, "action_key_changed", candidate_digest)
        return ProofAdoptionDecision(True, "candidate_adopted", candidate_digest)
