"""Clock port: monotonic timing and UTC wall-clock for freshness/timeout math.

The core never calls :func:`time.time` or :func:`time.monotonic` directly
outside this module, so a test can substitute a deterministic clock instead
of depending on real wall-clock time.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> str:
        """Return the current UTC time as ``YYYY-MM-DDTHH:MM:SS.ffffffZ``."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic timestamp in seconds, only valid for deltas."""
        ...


class SystemClock:
    """Default :class:`Clock` backed by the stdlib ``time``/``datetime``."""

    def now_utc(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def monotonic(self) -> float:
        return time.monotonic()
