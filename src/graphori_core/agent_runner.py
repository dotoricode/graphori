"""AgentRunner port: runs one Attempt's non-interactive command to completion.

This ties the ``ProcessSupervisor`` port to the canonical ``Attempt`` state
machine (:mod:`graphori_core.compiler`) so a generic terminal adapter can
dispatch a worker without any Orca dependency. It never invents a new
transition table -- ``transition_attempt`` from the compiler remains the
single source of truth for what states an attempt may reach.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

from .clock import Clock, SystemClock
from .compiler import StateTransitionError, transition_attempt
from .models import Attempt, AttemptState
from .process_supervisor import DEFAULT_ENV_ALLOWLIST, ProcessLimits, ProcessResult, ProcessSupervisor


@dataclass(frozen=True)
class AttemptOutcome:
    attempt: Attempt
    process: ProcessResult

    def worker_finished_payload(self) -> dict[str, Any]:
        """The ``worker_finished`` event payload for this outcome.

        Bytes are never embedded directly; only their digests and truncation
        flags are, matching the evidence-normalization rule in
        PORTABILITY_CONTRACT.md (no raw secrets/paths leak into the journal).
        """
        process = self.process
        return {
            "attempt_id": self.attempt.attempt_id,
            "attempt_state": self.attempt.state.value,
            "exit_code": process.exit_code,
            "timed_out": process.timed_out,
            "duration_seconds": process.duration_seconds,
            "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
            "stdout_truncated": process.stdout_truncated,
            "stderr_truncated": process.stderr_truncated,
            "stdout_total_bytes": process.stdout_total_bytes,
            "stderr_total_bytes": process.stderr_total_bytes,
            "tree_kill_used": process.tree_kill_used,
            "tree_kill_method": process.tree_kill_method,
            "tree_kill_evidence": process.tree_kill_evidence,
            "dropped_env_keys": list(process.dropped_env_keys),
        }


@dataclass
class AgentRunner:
    """Runs one Attempt's argv to completion and updates its terminal state."""

    supervisor: ProcessSupervisor
    clock: Clock | None = None

    def __post_init__(self) -> None:
        if self.clock is None:
            self.clock = SystemClock()

    def run_attempt(self, attempt: Attempt, *, argv: Sequence[str],
                    workspace_root: Any, cwd: Any = ".", env: Mapping[str, str] | None = None,
                    env_allowlist: frozenset = DEFAULT_ENV_ALLOWLIST,
                    limits: ProcessLimits = ProcessLimits()) -> AttemptOutcome:
        if attempt.state is AttemptState.PLANNED:
            transition_attempt(attempt, AttemptState.DISPATCHED)
        if attempt.state is AttemptState.DISPATCHED:
            transition_attempt(attempt, AttemptState.RUNNING)
        if attempt.state is not AttemptState.RUNNING:
            raise StateTransitionError(
                f"attempt {attempt.attempt_id} must be running before it can be executed, "
                f"got {attempt.state}"
            )

        result = self.supervisor.run(
            argv, workspace_root=workspace_root, cwd=cwd, env=env,
            env_allowlist=env_allowlist, limits=limits,
        )

        if result.timed_out:
            transition_attempt(attempt, AttemptState.TIMED_OUT)
            transition_attempt(attempt, AttemptState.OUTCOME_UNKNOWN)
        elif result.exit_code == 0:
            transition_attempt(attempt, AttemptState.SUCCEEDED)
        else:
            transition_attempt(attempt, AttemptState.FAILED)

        return AttemptOutcome(attempt, result)
