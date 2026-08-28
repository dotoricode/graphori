"""Shared types for provider-owned structured event streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .agent_contract import WorkerReport


class ProviderProtocolError(ValueError):
    """Raised when a provider stream cannot be interpreted safely."""


@dataclass(frozen=True)
class NormalizedProviderEvent:
    provider: str
    event_type: str
    known: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderParseResult:
    provider: str
    events: tuple[NormalizedProviderEvent, ...]
    report: WorkerReport | None = None
    session_id: str = ""
    observed_model: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    provider_reported_cost_usd: float | None = None


def decode_json_lines(data: bytes) -> tuple[Mapping[str, Any], ...]:
    """Decode a provider JSONL stream without accepting terminal-text noise."""

    import json

    decoded: list[Mapping[str, Any]] = []
    for number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderProtocolError(f"malformed provider JSON on line {number}") from exc
        if not isinstance(value, Mapping):
            raise ProviderProtocolError(f"provider event on line {number} is not an object")
        decoded.append(value)
    return tuple(decoded)


def parse_report(value: Any, *, provider: str) -> WorkerReport:
    try:
        return WorkerReport.from_mapping(value)
    except ValueError as exc:
        raise ProviderProtocolError(f"invalid {provider} final WorkerReport") from exc
