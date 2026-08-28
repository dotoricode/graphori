"""Read-only Orca CLI adapter.

This package deliberately talks to Orca only through its public JSON CLI.
"""

from .adapter import OrcaAdapter, AdapterUnavailable, CliResponse, normalize_snapshot
from .bridge import OrcaJournalBridge
from .capabilities import AdapterHealth, AdapterHealthState
from .client import OrcaClient, resolve_orca_executable
from .execution import (
    OrcaBinding,
    OrcaExecutionAdapter,
    ReconciliationStatus,
    RuntimeResourceOwnership,
)
from graphori_core.orca_lifecycle import OrcaLaunchStrategy

__all__ = [
    "AdapterHealth", "AdapterHealthState", "AdapterUnavailable", "CliResponse",
    "OrcaAdapter", "OrcaBinding", "OrcaClient", "OrcaExecutionAdapter",
    "OrcaLaunchStrategy",
    "OrcaJournalBridge", "ReconciliationStatus", "normalize_snapshot",
    "resolve_orca_executable", "RuntimeResourceOwnership",
]
