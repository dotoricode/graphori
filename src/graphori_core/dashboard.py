"""Small, dependency-free dashboard HTTP/SSE adapter.

The journal remains the source of truth.  This module only renders validated
events and keeps a bounded in-memory replay buffer for live subscribers.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Condition, RLock
from urllib.parse import parse_qs, unquote, urlsplit
import json
import mimetypes
import time

from .journal import ensure_run_dirs, replay_journal
from .projection import (
    CanonicalRunProjection, build_canonical_projection, effective_plan, fresh_reducer,
    replay_node_role_ids, replay_task_id, resolve_projection_metadata,
)
from .scheduler import (
    Scheduler, SchedulerPolicy, SchedulingBatch, SchedulingState,
    projected_proof_states,
)


def _now() -> float:
    return time.time()


def _event_time(event):
    value = event.get("recorded_at") or event.get("occurred_at")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, TypeError, ValueError):
        return _now()


def _elapsed_ms(start: str | None, finish: str | None) -> int | None:
    if not start or not finish:
        return None
    try:
        return max(0, round((_event_time({"recorded_at": finish}) - _event_time({"recorded_at": start})) * 1000))
    except (TypeError, ValueError):
        return None


def _provider_progress(events, node_id=None):
    """Provider progress is optional telemetry, never inferred from node state."""
    for event in reversed(events):
        if event.get("type") not in {"progress_reported", "progress"}:
            continue
        payload = event.get("payload") or {}
        entity = event.get("entity") or {}
        event_node = entity.get("node_id") or payload.get("node_id")
        if node_id is not None and event_node != node_id:
            continue
        percent = payload.get("percent")
        if isinstance(percent, (int, float)) and 0 <= percent <= 100:
            return {"state": "reported", "percent": percent,
                    "updated_at": event.get("recorded_at"), "source": "provider"}
        return {"state": "reported", "percent": None,
                "updated_at": event.get("recorded_at"), "source": "provider"}
    return {"state": "unknown", "percent": None, "updated_at": None, "source": None}


class DashboardStore:
    """Read journals and maintain a bounded event replay cache per run."""

    def __init__(self, root, *, static_dir=None, replay_limit=256,
                 stale_after=30.0, heartbeat_interval=15.0):
        self.root = Path(root).resolve()
        self.static_dir = Path(static_dir).resolve() if static_dir else None
        self.replay_limit = int(replay_limit)
        self.stale_after = float(stale_after)
        self.heartbeat_interval = float(heartbeat_interval)
        self._cache = {}
        self._condition = Condition(RLock())

    def _events(self, run_id):
        paths = ensure_run_dirs(self.root, run_id)
        events, digest = replay_journal(paths)
        with self._condition:
            old = self._cache.get(run_id)
            latest = events[-self.replay_limit:]
            if old != latest:
                self._cache[run_id] = latest
                self._condition.notify_all()
            return events, digest

    def canonical_projection(self, run_id) -> tuple[CanonicalRunProjection, list[dict]]:
        events, journal_digest = self._events(run_id)
        metadata = resolve_projection_metadata(self.root, run_id, events)
        spec, published_plan = metadata.spec, metadata.plan
        reducer = fresh_reducer(
            published_plan,
            task_id=replay_task_id(events, default=f"task:{published_plan.run_id}"),
            node_role_ids=replay_node_role_ids(events),
        )
        for event in events:
            reducer.apply(event)
        plan = effective_plan(published_plan, events)
        if reducer.run is not None and reducer.run.terminal_status is None:
            policy_value = next((
                (event.get("payload") or {}).get("scheduler_policy")
                for event in events if event.get("type") == "graph_published"
                and isinstance((event.get("payload") or {}).get("scheduler_policy"), dict)
            ), None)
            policy = (SchedulerPolicy(**policy_value) if policy_value is not None
                      else SchedulerPolicy(max_wip=spec.constraints.max_parallelism))
            scheduler = Scheduler(policy)
            node_states = {
                node_id: node.state.value for node_id, node in reducer.run.graph.nodes.items()
            }
            scheduling = scheduler.decide(plan, SchedulingState(
                node_states=node_states,
                approved_nodes=frozenset(reducer.approved_nodes),
                proof_states=projected_proof_states(plan, node_states),
            ))
        else:
            scheduling = SchedulingBatch()
        projection = build_canonical_projection(
            spec=spec, published_plan=published_plan, plan=plan, reducer=reducer,
            events=events, journal_digest=journal_digest, scheduling=scheduling,
        )
        return replace(projection, metadata_provenance=metadata.provenance), events

    def snapshot(self, run_id):
        projection, events = self.canonical_projection(run_id)
        snapshot = projection.to_dict()
        heartbeat = projection.last_heartbeat_at
        heartbeat_time = _event_time({"recorded_at": heartbeat}) if heartbeat else None
        age = None if heartbeat_time is None else max(0.0, _now() - heartbeat_time)
        liveness = "completed" if projection.terminal_status else "unknown" if age is None else (
            "heartbeat_recent" if age <= self.stale_after else "stale"
        )
        # Connection age is transport metadata and intentionally excluded from
        # the canonical projection digest.
        snapshot["connection"] = {
            "status": ("stale" if liveness == "stale" else
                       "fresh" if liveness == "heartbeat_recent" else liveness),
            "last_event_id": str(projection.snapshot_seq) if events else None,
        }
        snapshot["liveness"] = {"status": liveness, "age_seconds": age}
        activity_at = projection.updated_at
        activity_age = None if not activity_at else max(
            0.0, _now() - _event_time({"recorded_at": activity_at}),
        )
        elapsed_end = projection.finished_at or datetime.fromtimestamp(
            _now(), tz=datetime.now().astimezone().tzinfo,
        ).isoformat()
        snapshot["activity"] = {
            "last_activity_at": activity_at,
            "last_activity_age_seconds": activity_age,
            "elapsed_ms": _elapsed_ms(projection.started_at, elapsed_end),
        }
        snapshot["provider_progress"] = _provider_progress(events)
        for node in snapshot.get("nodes", []):
            node_activity_at = (node.get("last_event") or {}).get("updatedAt")
            node["activity"] = {
                "last_activity_at": node_activity_at,
                "last_activity_age_seconds": (
                    None if not node_activity_at else max(
                        0.0, _now() - _event_time({"recorded_at": node_activity_at}),
                    )
                ),
                "elapsed_ms": _elapsed_ms(
                    node.get("started_at"),
                    node.get("finished_at") or (elapsed_end if node.get("status") in {
                        "assigned", "running", "awaiting_verification",
                    } else None),
                ),
            }
            node["liveness"] = {
                "status": liveness if node.get("status") in {"assigned", "running"} else "not_running",
            }
            node["provider_progress"] = _provider_progress(events, node.get("node_id"))
        snapshot["heartbeat"] = {
            "updatedAt": heartbeat, "age_seconds": age, "status": liveness,
        }
        snapshot["graph_version"] = projection.plan_version
        return snapshot, events

    def replay_after(self, run_id, since):
        self.snapshot(run_id)
        with self._condition:
            events = list(self._cache.get(run_id, ()))
        if not events:
            return [], False
        oldest = events[0]["seq"]
        gap = since < oldest - 1
        return [e for e in events if e["seq"] > since], gap


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "GraphoriDashboard/1"

    @property
    def store(self):
        return self.server.dashboard_store

    def _json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        parsed = urlsplit(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        try:
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "snapshot":
                self._json(self.store.snapshot(parts[1])[0]); return
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "events":
                self._sse(parts[1], parse_qs(parsed.query)); return
            if not parts and self.store.static_dir:
                parts = ["index.html"]
            self._static(parts)
        except (FileNotFoundError, ValueError, OSError):
            self.send_error(404)

    def _sse(self, run_id, query):
        since_values = query.get("since_seq", [])
        try: since = int(since_values[-1]) if since_values else int(self.headers.get("Last-Event-ID", "-1"))
        except ValueError: since = -1
        snapshot, _ = self.store.snapshot(run_id)
        replay, gap = self.store.replay_after(run_id, since)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no"); self.end_headers()
        try:
            self._write_event("snapshot", snapshot["snapshot_seq"], snapshot)
            if gap:
                oldest = replay[0]["seq"] if replay else snapshot["snapshot_seq"] + 1
                self._write_event("replay_gap", snapshot["snapshot_seq"], {"since_seq": since, "oldest_seq": oldest})
                return
            last_seq = since
            for event in replay:
                self._write_event("event", event["seq"], event)
                last_seq = max(last_seq, event["seq"])
            self._write_event("heartbeat", snapshot["snapshot_seq"], {"ts": _now()})
            last_heartbeat = _now()
            while True:
                time.sleep(0.5)
                pending, stream_gap = self.store.replay_after(run_id, last_seq)
                if stream_gap:
                    latest, _ = self.store.snapshot(run_id)
                    self._write_event("replay_gap", latest["snapshot_seq"],
                                      {"since_seq": last_seq, "oldest_seq": pending[0]["seq"] if pending else None})
                    return
                for event in pending:
                    self._write_event("event", event["seq"], event)
                    last_seq = event["seq"]
                if _now() - last_heartbeat >= self.store.heartbeat_interval:
                    latest, _ = self.store.snapshot(run_id)
                    self._write_event("heartbeat", latest["snapshot_seq"], {"ts": _now()})
                    last_heartbeat = _now()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _write_event(self, name, seq, data):
        self.wfile.write((f"event: {name}\nid: {seq}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n").encode()); self.wfile.flush()

    def _static(self, parts):
        if not self.store.static_dir or any(p in ("", ".", "..") or "/" in p or "\\" in p for p in parts): raise FileNotFoundError()
        root = self.store.static_dir; candidate = (root.joinpath(*parts)).resolve()
        candidate.relative_to(root)
        if not candidate.is_file(): raise FileNotFoundError()
        data = candidate.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *_): pass


def create_server(root, host="127.0.0.1", port=0, **kwargs):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.daemon_threads = True
    server.dashboard_store = DashboardStore(root, **kwargs)
    return server


__all__ = ["DashboardStore", "DashboardHandler", "create_server"]
