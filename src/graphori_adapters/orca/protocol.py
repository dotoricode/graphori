"""Validation helpers for Orca's JSON response envelope."""

from __future__ import annotations

from typing import Any, Mapping


class OrcaProtocolError(ValueError):
    pass


def result_object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OrcaProtocolError("Orca response must be an object")
    result = value.get("result")
    if not isinstance(result, Mapping):
        raise OrcaProtocolError("Orca response result must be an object")
    return result


def nested_id(value: Mapping[str, Any], *paths: tuple[str, ...]) -> str:
    for path in paths:
        current: Any = value
        for key in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(key)
        if isinstance(current, str) and current:
            return current
    raise OrcaProtocolError(f"Orca response is missing identity: {paths!r}")


def rows(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
    result = result_object(value)
    items = result.get(name, ())
    if not isinstance(items, list):
        raise OrcaProtocolError(f"Orca result.{name} must be an array")
    return tuple(item for item in items if isinstance(item, Mapping))
