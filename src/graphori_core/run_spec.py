"""Portable input contract for a Graphori v2 run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import re
from typing import Any, Mapping


_CRITERION_ID = re.compile(r"^[A-Z][A-Z0-9_]*-[0-9]+$")


def criterion_id(value: str) -> str:
    """Return the stable criterion id from ``ID: human readable text``.

    Criteria intentionally remain strings in the v2 schema.  This makes the
    addition backwards compatible while still giving every criterion an ID
    that can be carried through prompts, evidence and the final projection.
    """
    identifier, separator, text = value.partition(":")
    if not separator or not text.strip() or not _CRITERION_ID.fullmatch(identifier.strip()):
        raise ValueError("acceptance criteria must use stable 'ID: description' form")
    return identifier.strip()


def extract_acceptance_criteria(value: str) -> tuple[str, ...]:
    """Extract explicit ``AC-N`` clauses from a natural-language request.

    This is intentionally syntactic. It does not invent criteria or ask an
    LLM to reinterpret prose; users can always pass structured criteria via
    the product CLI instead.
    """

    matches = list(re.finditer(r"\b(AC-[0-9]+)\s*(?::|[-–—])?\s*", value))
    criteria: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        description = value[match.end():end].strip().strip(".;, \n\t")
        if description:
            criteria.append(f"{match.group(1)}: {description}")
    return tuple(criteria)


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(sorted(unknown))}")


@dataclass(frozen=True)
class RunConstraints:
    time_budget_ms: int | None = None
    cost_budget_usd: float | None = None
    max_parallelism: int = 3
    allow_external_effects: bool = False
    allow_network: bool = True

    def __post_init__(self) -> None:
        if self.max_parallelism < 1:
            raise ValueError("max_parallelism must be at least 1")
        if self.time_budget_ms is not None and self.time_budget_ms < 0:
            raise ValueError("time_budget_ms cannot be negative")
        if (self.cost_budget_usd is not None
                and (not math.isfinite(self.cost_budget_usd) or self.cost_budget_usd < 0)):
            raise ValueError("cost_budget_usd must be finite and non-negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunConstraints":
        _reject_unknown(value, set(cls.__dataclass_fields__), "constraint")
        return cls(**value)


@dataclass(frozen=True)
class PremiumPolicy:
    requires_approval: tuple[str, ...] = (
        "gpt-5.6-sol-*", "claude-opus-*", "tier:frontier",
    )
    approval_scope: str = "node"

    def __post_init__(self) -> None:
        if self.approval_scope != "node":
            raise ValueError("v2 only supports node-scoped premium approval")
        object.__setattr__(self, "requires_approval", tuple(sorted(set(self.requires_approval))))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PremiumPolicy":
        _reject_unknown(value, set(cls.__dataclass_fields__), "premium policy")
        data = dict(value)
        if "requires_approval" in data:
            data["requires_approval"] = tuple(data["requires_approval"])
        return cls(**data)


@dataclass(frozen=True)
class RunSpec:
    objective: str
    host: str
    workspace: str
    constraints: RunConstraints = field(default_factory=RunConstraints)
    premium_policy: PremiumPolicy = field(default_factory=PremiumPolicy)
    runtime_preference: tuple[str, ...] = (
        "native_host", "generic_process",
    )
    acceptance_criteria: tuple[str, ...] = ()
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError(f"unsupported RunSpec schema_version: {self.schema_version}")
        if not self.objective.strip():
            raise ValueError("objective must be non-empty")
        if not self.host.strip() or not self.workspace.strip():
            raise ValueError("host and workspace must be non-empty")
        if not self.runtime_preference:
            raise ValueError("runtime_preference must be non-empty")
        criteria = tuple(sorted(set(self.acceptance_criteria)))
        ids = [criterion_id(item) for item in criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("acceptance criterion IDs must be unique")
        object.__setattr__(self, "acceptance_criteria", criteria)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "objective": self.objective,
            "host": self.host,
            "workspace": self.workspace,
            "constraints": asdict(self.constraints),
            "premium_policy": {
                "requires_approval": list(self.premium_policy.requires_approval),
                "approval_scope": self.premium_policy.approval_scope,
            },
            "runtime_preference": list(self.runtime_preference),
            "acceptance_criteria": list(self.acceptance_criteria),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunSpec":
        _reject_unknown(value, set(cls.__dataclass_fields__), "RunSpec")
        data = dict(value)
        data["constraints"] = RunConstraints.from_dict(data.get("constraints", {}))
        data["premium_policy"] = PremiumPolicy.from_dict(data.get("premium_policy", {}))
        if "runtime_preference" in data:
            data["runtime_preference"] = tuple(data["runtime_preference"])
        if "acceptance_criteria" in data:
            data["acceptance_criteria"] = tuple(data["acceptance_criteria"])
        return cls(**data)

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode()).hexdigest()
