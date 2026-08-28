"""Truthful, component-level health for the Orca execution adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class AdapterHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class AdapterHealth:
    components: dict[str, AdapterHealthState] = field(default_factory=lambda: {
        "create_run": AdapterHealthState.UNAVAILABLE,
        "create_task": AdapterHealthState.UNAVAILABLE,
        "dispatch": AdapterHealthState.UNAVAILABLE,
        "delivery": AdapterHealthState.UNAVAILABLE,
        "release": AdapterHealthState.UNAVAILABLE,
        "cancel": AdapterHealthState.UNAVAILABLE,
        "reconcile": AdapterHealthState.UNAVAILABLE,
    })
    reasons: dict[str, str] = field(default_factory=dict)

    def set(self, component: str, state: AdapterHealthState, reason: str = "") -> None:
        self.components[component] = state
        if reason:
            self.reasons[component] = reason
        else:
            self.reasons.pop(component, None)

    def snapshot(self) -> Mapping[str, str]:
        return {key: value.value for key, value in sorted(self.components.items())}
