"""Read-only, failure-contained adapter for the public Orca CLI contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import subprocess
from typing import Any, Mapping, Sequence
import uuid

_TYPES = {
    "run": "run_created", "run_created": "run_created",
    "graph": "graph_published", "graph_published": "graph_published",
    "task": "node_status_changed", "task_status": "node_status_changed",
    "dispatch": "attempt_dispatched", "attempt_dispatched": "attempt_dispatched",
    "heartbeat": "heartbeat", "worker_done": "worker_finished",
    "worker_finished": "worker_finished", "gate": "gate_resolved",
    "gate_resolved": "gate_resolved", "progress": "progress_reported",
    "status": "node_status_changed",
}
_KNOWN_PAYLOAD = {
    "status", "state", "outcome", "verdict", "reason", "evidence_ids",
    "evidence_id", "progress", "message", "checkpoint", "output_digest",
    "argv", "cwd", "exit_code", "timed_out", "files_modified", "report_path",
}


class AdapterUnavailable(RuntimeError):
    """The external adapter could not provide trustworthy JSON."""


@dataclass(frozen=True)
class CliResponse:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _id(record: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        for key in ("events", "items", "tasks", "messages", "runs", "data"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, Mapping)]
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def normalize_snapshot(snapshot: Any, *, run_id: str = "run_orca", task_id: str = "task_orca",
                       platform: str = "windows") -> list[dict[str, Any]]:
    """Project connected output or a fixture into identical producer envelopes.

    Unknown fields are intentionally discarded. Missing identities become a
    quarantined event rather than an invented successful observation.
    """
    result: list[dict[str, Any]] = []
    for index, record in enumerate(_records(snapshot), 1):
        rid = _id(record, "run_id", "runId") or run_id
        tid = _id(record, "task_id", "taskId", "id") or task_id
        kind = str(record.get("type", record.get("event", record.get("kind", "status")))).lower()
        event_type = _TYPES.get(kind)
        missing = []
        if not _id(record, "run_id", "runId") and not run_id: missing.append("run_id")
        if not _id(record, "task_id", "taskId", "id") and not task_id: missing.append("task_id")
        if event_type is None: missing.append("event_type")
        if missing:
            event_type = "event_quarantined"
        payload = {key: record[key] for key in _KNOWN_PAYLOAD if key in record}
        if event_type == "event_quarantined":
            payload = {"reason": "adapter_unavailable", "missing_fields": missing,
                       "source_type": kind}
        else:
            payload["source"] = "orca_cli"
        actor_role = "human_gate" if event_type == "gate_resolved" else "worker"
        entity = {"task_id": tid}
        for key in ("node_id", "attempt_id", "gate_id"):
            value = _id(record, key)
            if value: entity[key] = value
        producer = _id(record, "producer_event_id", "message_id", "event_id") or f"orca:{rid}:{index}"
        event_id = _id(record, "event_id", "id") or "evt_" + uuid.uuid5(uuid.NAMESPACE_URL, producer).hex
        result.append({"schema_version": 1, "event_id": event_id,
                       "producer_event_id": producer, "run_id": rid, "graph_version": 1,
                       "occurred_at": _id(record, "occurred_at", "timestamp", "created_at") or _now(),
                       "actor": {"role": actor_role, "role_id": _id(record, "actor_id", "worker_id") or "role_orca"},
                       "type": event_type, "entity": entity, "payload": payload,
                       "usage": {"status": "unknown"}, "platform": platform})
    if not result:
        result.append({"schema_version": 1, "event_id": "evt_" + uuid.uuid4().hex,
                       "producer_event_id": "orca:empty", "run_id": run_id, "graph_version": 1,
                       "occurred_at": _now(), "actor": {"role": "observer", "role_id": "role_orca"},
                       "type": "event_quarantined", "entity": {"task_id": task_id},
                       "payload": {"reason": "adapter_unavailable", "missing_fields": ["response"]},
                       "usage": {"status": "unknown"}, "platform": platform})
    return result


class OrcaAdapter:
    """Explicit-argv, bounded, read-only Orca CLI client."""

    def __init__(self, executable: str = "orca", *, timeout: float = 10.0, runner=None):
        self.executable, self.timeout, self._runner = executable, timeout, runner

    def call(self, args: Sequence[str]) -> CliResponse:
        argv = (self.executable, *args)
        if self._runner is not None:
            return self._runner(argv, self.timeout)
        try:
            completed = subprocess.run(argv, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace",
                                       timeout=self.timeout, shell=False)
            return CliResponse(argv, completed.returncode, completed.stdout, completed.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CliResponse(argv, -1, "", "", type(exc).__name__)

    def read_json(self, args: Sequence[str]) -> tuple[Any | None, CliResponse]:
        response = self.call(args)
        if not response.ok:
            return None, response
        try:
            return json.loads(response.stdout), response
        except (TypeError, ValueError):
            return None, CliResponse(response.argv, response.returncode, response.stdout,
                                     response.stderr, "malformed_json")

    def status(self) -> tuple[Any | None, CliResponse]:
        return self.read_json(("status", "--json"))

    def run_show(self, run_id: str) -> tuple[Any | None, CliResponse]:
        return self.read_json(("orchestration", "run-show", "--id", run_id, "--json"))

    def task_list(self, run_id: str | None = None) -> tuple[Any | None, CliResponse]:
        args = ["orchestration", "task-list", "--json"]
        if run_id: args.extend(("--run", run_id))
        return self.read_json(args)

    def project(self, snapshot: Any, *, run_id: str = "run_orca", task_id: str = "task_orca") -> list[dict[str, Any]]:
        return normalize_snapshot(snapshot, run_id=run_id, task_id=task_id)
