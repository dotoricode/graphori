"""Monotonic acceptance-contract compilation over existing proof obligations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json

from .run_spec import criterion_id
from .sprout import ProofObligation


class AcceptanceSource(str, Enum):
    USER = "user"
    REPOSITORY = "repository"
    DETERMINISTIC = "deterministic"
    LLM = "llm"


_SOURCE_ORDER = {source: index for index, source in enumerate(AcceptanceSource)}


@dataclass(frozen=True)
class AcceptanceProof:
    """One proof required or proposed for an acceptance criterion."""

    criterion: str
    proof: ProofObligation
    source: AcceptanceSource | str
    mandatory: bool = True

    def __post_init__(self) -> None:
        identifier = criterion_id(self.criterion)
        try:
            source = AcceptanceSource(self.source)
        except ValueError as exc:
            raise ValueError("invalid acceptance proof source") from exc
        if not isinstance(self.mandatory, bool):
            raise ValueError("acceptance proof mandatory must be boolean")
        object.__setattr__(self, "criterion", self.criterion.strip())
        object.__setattr__(self, "source", source)
        if not identifier:
            raise ValueError("acceptance proof criterion must have a stable ID")

    @property
    def criterion_id(self) -> str:
        return criterion_id(self.criterion)

    def to_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion,
            "criterion_id": self.criterion_id,
            "mandatory": self.mandatory,
            "proof": {
                "obligation_id": self.proof.obligation_id,
                "verifier": self.proof.verifier,
            },
            "source": self.source.value,
        }


@dataclass(frozen=True)
class AcceptanceContract:
    """An immutable, replayable set of monotonically accumulated proofs."""

    proofs: tuple[AcceptanceProof, ...]
    used_v2_fallback: bool = False
    fallback_reason: str = ""

    def __post_init__(self) -> None:
        ordered = tuple(sorted(
            self.proofs,
            key=lambda item: (
                _SOURCE_ORDER[item.source], item.criterion_id,
                item.proof.obligation_id, item.proof.verifier,
            ),
        ))
        keys = [(item.criterion_id, item.proof.obligation_id) for item in ordered]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate acceptance proof identity")
        if self.used_v2_fallback != bool(self.fallback_reason):
            raise ValueError("v2 fallback status and reason must agree")
        object.__setattr__(self, "proofs", ordered)

    @property
    def mandatory_proofs(self) -> tuple[AcceptanceProof, ...]:
        return tuple(item for item in self.proofs if item.mandatory)

    def canonical_json(self) -> str:
        return json.dumps({
            "fallback_reason": self.fallback_reason,
            "proofs": [item.to_dict() for item in self.proofs],
            "used_v2_fallback": self.used_v2_fallback,
        }, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()


class AcceptanceContractCompiler:
    """Add proof layers in trust order without deleting or rewriting earlier proofs."""

    @staticmethod
    def user_proofs(criteria: tuple[str, ...]) -> tuple[AcceptanceProof, ...]:
        return tuple(AcceptanceProof(
            criterion=item,
            proof=ProofObligation(f"criterion:{criterion_id(item)}", "v2-verifier"),
            source=AcceptanceSource.USER,
        ) for item in criteria)

    def compile(
            self, *, user: tuple[AcceptanceProof, ...],
            repository: tuple[AcceptanceProof, ...] = (),
            deterministic: tuple[AcceptanceProof, ...] = (),
            llm: tuple[AcceptanceProof, ...] = ()) -> AcceptanceContract:
        layers = (
            (AcceptanceSource.USER, user),
            (AcceptanceSource.REPOSITORY, repository),
            (AcceptanceSource.DETERMINISTIC, deterministic),
            (AcceptanceSource.LLM, llm),
        )
        v2 = self._v2_contract(user)
        accumulated: dict[tuple[str, str], AcceptanceProof] = {}
        criterion_text: dict[str, str] = {}
        for expected_source, proofs in layers:
            for item in proofs:
                if item.source is not expected_source:
                    return replace(
                        v2, used_v2_fallback=True,
                        fallback_reason="acceptance_source_mismatch",
                    )
                prior_text = criterion_text.get(item.criterion_id)
                if prior_text is not None and prior_text != item.criterion:
                    return replace(
                        v2, used_v2_fallback=True,
                        fallback_reason="criterion_text_conflict",
                    )
                criterion_text[item.criterion_id] = item.criterion
                key = (item.criterion_id, item.proof.obligation_id)
                prior = accumulated.get(key)
                if prior is None:
                    accumulated[key] = item
                    continue
                if prior.proof.verifier != item.proof.verifier:
                    return replace(
                        v2, used_v2_fallback=True,
                        fallback_reason="proof_meaning_conflict",
                    )
                # A later layer may make an existing proof mandatory, but can
                # never make a mandatory proof optional or change its owner.
                accumulated[key] = replace(
                    prior, mandatory=prior.mandatory or item.mandatory,
                )
        return AcceptanceContract(tuple(accumulated.values()))

    @staticmethod
    def _v2_contract(user: tuple[AcceptanceProof, ...]) -> AcceptanceContract:
        user_only: dict[tuple[str, str], AcceptanceProof] = {}
        for item in user:
            if item.source is not AcceptanceSource.USER:
                continue
            key = (item.criterion_id, item.proof.obligation_id)
            prior = user_only.get(key)
            if prior is None or (not prior.mandatory and item.mandatory):
                user_only[key] = item
        return AcceptanceContract(tuple(user_only.values()))
