"""Diagnostic Orca lifecycle evidence and version-scoped route isolation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


class LifecycleFailureStage(str, Enum):
    PROCESS_NOT_STARTED = "process_not_started"
    AGENT_NOT_READY = "agent_not_ready"
    INSTRUCTION_NOT_DELIVERED = "instruction_not_delivered"
    INSTRUCTION_DELIVERED = "instruction_delivered"
    LIFECYCLE_NOT_PROVEN = "lifecycle_not_proven"
    WORK_COMPLETED = "work_completed"
    WORKER_DONE_NOT_EMITTED = "worker_done_not_emitted"
    WORKER_DONE_EMITTED = "worker_done_emitted"
    DELIVERY_NOT_OBSERVED = "delivery_not_observed"
    DELIVERY_OBSERVED = "delivery_observed"
    GRAPHORI_NOT_CORRELATED = "graphori_not_correlated"
    COMPLETE = "complete"


@dataclass(frozen=True)
class OrcaLifecycleTimeline:
    run_create_at: str | None = None
    task_create_at: str | None = None
    worker_start_requested_at: str | None = None
    worker_start_returned_at: str | None = None
    terminal_handle_observed_at: str | None = None
    agent_process_observed_at: str | None = None
    first_terminal_activity_at: str | None = None
    sentinel_created_at: str | None = None
    agent_exit_observed_at: str | None = None
    worker_done_observed_at: str | None = None
    delivery_observed_at: str | None = None
    journaled_at: str | None = None
    acked_at: str | None = None
    released_at: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OrcaLifecycleTimeline":
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown Orca timeline fields: {sorted(unknown)}")
        return cls(**value)


@dataclass(frozen=True)
class InstructionDeliveryEvidence:
    provider: str
    arm: str
    nonce: str
    process_started: bool | None = None
    agent_ready: bool | None = None
    instruction_sent: bool | None = None
    task_effect_observed: bool | None = None
    lifecycle_contract_observed: bool | None = None
    completion_attempt_observed: bool | None = None
    worker_done_observed: bool | None = None
    delivery_observed: bool | None = None
    graphori_correlated: bool | None = None
    timeline: OrcaLifecycleTimeline = OrcaLifecycleTimeline()
    diagnostic_refs: tuple[str, ...] = ()

    @property
    def stage(self) -> LifecycleFailureStage:
        timeline = self.timeline
        if all((
                self.delivery_observed is True,
                self.graphori_correlated is True,
                timeline.journaled_at,
                timeline.acked_at,
                timeline.released_at)):
            return LifecycleFailureStage.COMPLETE
        if self.delivery_observed is True and self.graphori_correlated is False:
            return LifecycleFailureStage.GRAPHORI_NOT_CORRELATED
        if self.delivery_observed is True:
            return LifecycleFailureStage.DELIVERY_OBSERVED
        if self.worker_done_observed is True:
            return LifecycleFailureStage.WORKER_DONE_EMITTED
        if self.completion_attempt_observed is True:
            return LifecycleFailureStage.DELIVERY_NOT_OBSERVED
        if self.task_effect_observed is True:
            if self.completion_attempt_observed is False:
                return LifecycleFailureStage.WORKER_DONE_NOT_EMITTED
            return LifecycleFailureStage.WORK_COMPLETED
        if self.instruction_sent is True:
            return LifecycleFailureStage.INSTRUCTION_DELIVERED
        if self.agent_ready is True:
            return LifecycleFailureStage.INSTRUCTION_NOT_DELIVERED
        if self.process_started is True:
            return LifecycleFailureStage.AGENT_NOT_READY
        return LifecycleFailureStage.PROCESS_NOT_STARTED

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stage"] = self.stage.value
        value["diagnostic_refs"] = list(self.diagnostic_refs)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InstructionDeliveryEvidence":
        data = dict(value)
        data.pop("stage", None)
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown instruction evidence fields: {sorted(unknown)}")
        data["timeline"] = OrcaLifecycleTimeline.from_dict(data.get("timeline", {}))
        data["diagnostic_refs"] = tuple(data.get("diagnostic_refs", ()))
        return cls(**data)


class RouteHealthStatus(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    RECHECK = "recheck"


class OrcaLaunchStrategy(str, Enum):
    DIRECT_CLI = "direct_cli"
    ORCA_COMPOSED = "orca_composed"
    ORCA_READY_TERMINAL = "orca_ready_terminal"


@dataclass(frozen=True)
class RouteHealthKey:
    orca_version: str
    runtime_id: str
    guide_digest: str
    agent_provider: str
    agent_version: str
    launch_strategy: OrcaLaunchStrategy = OrcaLaunchStrategy.ORCA_COMPOSED

    def __post_init__(self) -> None:
        if not isinstance(self.launch_strategy, OrcaLaunchStrategy):
            object.__setattr__(
                self, "launch_strategy", OrcaLaunchStrategy(self.launch_strategy),
            )
        if not all(asdict(self).values()):
            raise ValueError("route health key fields must be explicit")

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RouteHealthRecord:
    key: RouteHealthKey
    status: RouteHealthStatus
    reason: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": asdict(self.key),
            "status": self.status.value,
            "reason": self.reason,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RouteHealthRecord":
        key = dict(value["key"])
        key.setdefault("launch_strategy", OrcaLaunchStrategy.ORCA_COMPOSED.value)
        return cls(
            RouteHealthKey(**key), RouteHealthStatus(value["status"]),
            str(value.get("reason", "")), str(value["observed_at"]),
        )


class RouteCircuitBreaker:
    """Persist exact environment-scoped route health without global bans."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records = self._load()

    def _load(self) -> dict[str, RouteHealthRecord]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema_version") not in {1, 2}:
            raise ValueError("unsupported route health schema")
        records = [RouteHealthRecord.from_dict(item) for item in value.get("records", ())]
        return {item.key.digest: item for item in records}

    def _save(self) -> None:
        payload = {
            "schema_version": 2,
            "records": [
                self._records[key].to_dict() for key in sorted(self._records)
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def record(self, key: RouteHealthKey, status: RouteHealthStatus,
               reason: str, *, observed_at: str | None = None) -> None:
        timestamp = observed_at or datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z",
        )
        self._records[key.digest] = RouteHealthRecord(key, status, reason, timestamp)
        self._save()

    def status(self, key: RouteHealthKey) -> RouteHealthStatus:
        record = self._records.get(key.digest)
        return record.status if record is not None else RouteHealthStatus.RECHECK

    def allows_pre_dispatch(self, key: RouteHealthKey) -> bool:
        return self.status(key) is not RouteHealthStatus.BLOCKED

    def select_pre_dispatch(
            self, candidates: Sequence[RouteHealthKey]) -> RouteHealthKey | None:
        return next((item for item in candidates if self.allows_pre_dispatch(item)), None)

    @staticmethod
    def allows_automatic_fallback(*, dispatch_started: bool, outcome: str) -> bool:
        del outcome
        return not dispatch_started

    def request_recheck(self, key: RouteHealthKey) -> None:
        self._records.pop(key.digest, None)
        self._save()
