"""Single-writer JSONL journal with tmp/ready inbox, idempotency and quarantine.

Producers append events to ``inbox/tmp`` then atomically rename into
``inbox/ready`` (:func:`submit_event`).  A single :class:`JournalWriter`
consumes ready files in a deterministic order, assigns monotonic ``seq``,
``recorded_at``, ``prev_digest`` and ``digest``, and appends canonical UTF-8
JSONL to the journal file.  Exact duplicates are ignored; conflicting
duplicates and malformed submissions are quarantined without ever touching
already-accepted journal entries.  This module intentionally reuses the
canonical envelope validator and event-type set from :mod:`graphori_core.reducer`
instead of inventing a second source of truth for envelope shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
import errno
import hashlib
import json
import os
import re
import time
import uuid

from .paths import resolve_run_root, safe_join
from .reducer import EVENT_TYPES, StateTransitionError, validate_event_envelope

GENESIS_DIGEST = "sha256:" + "0" * 64

# Width of the submission stamp that opens a ready filename. Nineteen digits
# hold nanoseconds since the epoch past the year 2200, and the fixed width
# keeps lexical order equal to numeric order.
_SUBMITTED_AT_DIGITS = 19
_SUBMITTED_AT = re.compile(r"^(\d{%d})\." % _SUBMITTED_AT_DIGITS)


def _submitted_at(path: Path) -> int | None:
    """Submission time in nanoseconds, read from the name, or None if legacy."""
    match = _SUBMITTED_AT.match(path.name)
    return int(match.group(1)) if match else None


# Windows reports a range already held by another process as EACCES; the
# retrying lock modes can also surface EDEADLOCK.  Every other errno means the
# lock could not be evaluated, which is a different failure and must not be
# reported to the user as "another Graphori is running".
_NT_CONTENTION_ERRNOS = frozenset(
    value for value in (getattr(errno, name, None) for name in ("EACCES", "EDEADLOCK", "EDEADLK"))
    if value is not None
)


class _UnsupportedLockPlatform(RuntimeError):
    """Raised when no advisory-lock backend exists for this platform."""


def _lock_backend():
    """Import this platform's lock module, or report the platform unsupported."""
    if os.name not in ("posix", "nt"):
        raise _UnsupportedLockPlatform(os.name)
    try:
        return __import__("fcntl" if os.name == "posix" else "msvcrt")
    except ImportError as exc:  # pragma: no cover - defensive
        raise _UnsupportedLockPlatform(os.name) from exc


def _lock_exclusive_nonblocking(fd: int) -> None:
    """Take a process-scoped exclusive advisory lock, or raise.

    ``BlockingIOError`` means another live writer holds the lock.  Any other
    ``OSError`` means the lock could not be evaluated at all, and
    ``_UnsupportedLockPlatform`` means there is no backend here.  Callers treat
    all three as fail-closed; only the first is reported as contention.
    """
    backend = _lock_backend()
    if os.name == "posix":
        backend.flock(fd, backend.LOCK_EX | backend.LOCK_NB)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        backend.locking(fd, backend.LK_NBLCK, 1)
    except OSError as exc:
        if exc.errno in _NT_CONTENTION_ERRNOS:
            raise BlockingIOError(str(exc)) from exc
        raise


def _unlock(fd: int) -> None:
    backend = _lock_backend()
    if os.name == "posix":
        backend.flock(fd, backend.LOCK_UN)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    backend.locking(fd, backend.LK_UNLCK, 1)

_PRODUCER_REQUIRED = (
    "schema_version", "event_id", "producer_event_id", "run_id", "graph_version",
    "occurred_at", "actor", "type", "entity", "payload",
)

_WRITER_ASSIGNED = ("seq", "recorded_at", "prev_digest", "digest")


class JournalOwnershipError(RuntimeError):
    """Raised when this process cannot exclusively own a canonical journal.

    The message is English so that the journal layer stays free of presentation
    choices.  ``key`` names the condition, and ``detail`` carries any
    platform text, so a caller that knows the user's language can render the
    same condition in it.
    """

    def __init__(self, message: str, *, key: str = "", detail: str = "") -> None:
        super().__init__(message)
        self.key = key
        self.detail = detail


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_clock() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def content_key(envelope: Mapping[str, Any]) -> str:
    """Digest of the producer-controlled fields, ignoring writer-assigned ones."""
    body = {k: v for k, v in envelope.items() if k not in _WRITER_ASSIGNED}
    # The writer materializes this protocol default in accepted envelopes.
    # Normalize producer submissions the same way so exact redelivery remains
    # idempotent after a writer/process restart.
    body.setdefault("usage", {"status": "unknown"})
    return _sha256_hex(_canonical_bytes(body))


def _validate_producer_envelope(envelope: Mapping[str, Any], run_id: str) -> None:
    if not isinstance(envelope, Mapping):
        raise StateTransitionError("submitted envelope must be an object")
    missing = [name for name in _PRODUCER_REQUIRED if name not in envelope]
    if missing:
        raise StateTransitionError(f"submitted envelope missing fields: {', '.join(missing)}")
    if envelope["run_id"] != run_id:
        raise StateTransitionError("submitted envelope run_id does not match this run")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise StateTransitionError("schema_version must be integer 1")
    if envelope["type"] not in EVENT_TYPES:
        raise StateTransitionError(f"unknown event type: {envelope['type']!r}")
    actor = envelope["actor"]
    if not isinstance(actor, Mapping) or not actor.get("role") or not actor.get("role_id"):
        raise StateTransitionError("actor.role and actor.role_id are required")
    entity = envelope["entity"]
    if not isinstance(entity, Mapping) or not entity.get("task_id"):
        raise StateTransitionError("entity.task_id is required")
    if not isinstance(envelope["payload"], Mapping):
        raise StateTransitionError("payload must be an object")
    if not isinstance(envelope["event_id"], str) or not envelope["event_id"].strip():
        raise StateTransitionError("event_id must be a non-empty string")
    if not isinstance(envelope["producer_event_id"], str) or not envelope["producer_event_id"].strip():
        raise StateTransitionError("producer_event_id must be a non-empty string")


@dataclass(frozen=True)
class RunPaths:
    root: Path
    run_id: str

    @property
    def run_root(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id)

    @property
    def tmp(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "inbox", "tmp")

    @property
    def ready(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "inbox", "ready")

    @property
    def journal_dir(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "journal")

    @property
    def journal_file(self) -> Path:
        return self.journal_dir / "journal.jsonl"

    @property
    def writer_lock_file(self) -> Path:
        """Stable advisory-lock inode for the canonical journal writer.

        This file intentionally remains after a clean close.  The OS lock,
        rather than file presence, represents ownership; removing it would
        permit lock split-brain through different inodes during a race.
        """
        return self.journal_dir / ".writer.lock"

    @property
    def evidence_dir(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "evidence")

    @property
    def quarantine_dir(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "quarantine")

    @property
    def projection_dir(self) -> Path:
        return safe_join(self.root, ".graphori", "runs", self.run_id, "projection")


def ensure_run_dirs(root: os.PathLike | str, run_id: str) -> RunPaths:
    paths = RunPaths(resolve_run_root(root), run_id)
    for directory in (paths.tmp, paths.ready, paths.journal_dir, paths.evidence_dir,
                      paths.quarantine_dir, paths.projection_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def _sanitize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value)) or "producer"


def submit_event(paths: RunPaths, envelope: Mapping[str, Any], *, local_seq: int) -> Path:
    """Write ``envelope`` to inbox/tmp then atomically rename it into inbox/ready."""
    _validate_producer_envelope(envelope, paths.run_id)
    producer_id = _sanitize_id(envelope["actor"]["role_id"])
    # The leading stamp is the submission ordinal the consumer sorts on. It is
    # nanoseconds since the epoch so that it stays comparable with st_mtime_ns
    # for any file left behind by an older version.
    name = (f"{time.time_ns():0{_SUBMITTED_AT_DIGITS}d}.{producer_id}"
            f".{local_seq:012d}.{uuid.uuid4().hex}.json")
    tmp_path = safe_join(paths.tmp, name)
    ready_path = safe_join(paths.ready, name)
    data = _canonical_bytes(dict(envelope))
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp_path), str(ready_path))
    return ready_path


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.name, ""
    counter = 1
    while path.exists():
        path = path.with_name(f"{stem}.dup{counter}{suffix}")
        counter += 1
    return path


def read_journal_lines(path: Path) -> tuple[list[dict[str, Any]], bytes | None]:
    """Parse a journal file, validating envelope shape and the hash chain.

    Returns ``(valid_events, corrupt_tail)``. ``corrupt_tail`` is the raw
    bytes of a truncated (newline-less) final line, preserved so the caller
    can quarantine it. A corrupt line anywhere else is fail-closed: this
    raises instead of silently dropping or approving it.
    """
    if not path.exists():
        return [], None
    raw = path.read_bytes()
    if not raw:
        return [], None
    ends_with_newline = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if ends_with_newline:
        lines = lines[:-1]
    events: list[dict[str, Any]] = []
    corrupt_tail: bytes | None = None
    for index, line in enumerate(lines):
        is_last = index == len(lines) - 1
        try:
            if not line.strip():
                raise ValueError("empty journal line")
            event = json.loads(line.decode("utf-8"))
            validate_event_envelope(event)
            if events:
                if event["prev_digest"] != events[-1]["digest"]:
                    raise StateTransitionError("hash chain broken: prev_digest mismatch")
            elif event["prev_digest"] != GENESIS_DIGEST:
                raise StateTransitionError("first journal entry must chain from the genesis digest")
            recomputed = "sha256:" + _sha256_hex(
                _canonical_bytes({k: v for k, v in event.items() if k != "digest"}))
            if recomputed != event["digest"]:
                raise StateTransitionError("digest does not match recomputed content hash")
        except Exception as exc:
            if is_last and not ends_with_newline:
                corrupt_tail = line
                break
            raise StateTransitionError(f"corrupt journal line at index {index}: {exc}") from exc
        events.append(event)
    return events, corrupt_tail


def replay_journal(paths: RunPaths) -> tuple[list[dict[str, Any]], str]:
    """Validate the hash chain and return ``(events, projection_digest)``.

    ``projection_digest`` is a deterministic function of the applied event
    stream, so two independent replays of the same journal always agree.
    """
    events, tail = read_journal_lines(paths.journal_file)
    if tail is not None:
        raise StateTransitionError(
            "journal has an unrecovered truncated tail; open it with JournalWriter first"
        )
    digest = _sha256_hex(_canonical_bytes([
        {"seq": e["seq"], "event_id": e["event_id"], "type": e["type"],
         "entity": e["entity"], "payload": e["payload"]}
        for e in events
    ]))
    return events, digest


@dataclass
class JournalWriter:
    """The single process allowed to append to ``journal.jsonl``."""

    paths: RunPaths
    clock: Callable[[], str] = field(default=_default_clock)
    _producer_seen: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _event_ids_seen: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _last_digest: str = field(default=GENESIS_DIGEST, init=False, repr=False)
    _next_seq: int = field(default=0, init=False, repr=False)
    _lock_fd: int | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.paths.journal_dir.mkdir(parents=True, exist_ok=True)
        self.paths.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_ownership()
        try:
            self._load_existing()
        except Exception:
            self.close()
            raise

    def _acquire_ownership(self) -> None:
        """Acquire a non-blocking, process-scoped exclusive advisory file lock.

        POSIX uses ``flock`` and Windows uses ``msvcrt.locking``; both release
        the lock when the descriptor closes or the process dies.  A platform
        with neither backend is fail-closed rather than treated as unowned.
        A successful acquire happens before recovery or journal reads that
        influence writer state, so a second writer cannot compute a competing
        seq or hash-chain head.
        """
        fd = os.open(str(self.paths.writer_lock_file), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _lock_exclusive_nonblocking(fd)
        except BaseException as exc:
            os.close(fd)
            if isinstance(exc, BlockingIOError):
                raise JournalOwnershipError(
                    "Another Graphori run owns this journal. Nothing was recorded.",
                    key="writer_busy",
                ) from exc
            if isinstance(exc, _UnsupportedLockPlatform):
                raise JournalOwnershipError(
                    "This platform has no journal writer lock, so running would "
                    "be unsafe.",
                    key="writer_unsupported",
                ) from exc
            if isinstance(exc, OSError):
                raise JournalOwnershipError(
                    "Could not acquire the journal writer lock, so the run "
                    f"stopped: {exc}",
                    key="writer_unavailable", detail=str(exc),
                ) from exc
            raise
        self._lock_fd = fd

    def _require_ownership(self) -> None:
        if self._closed or self._lock_fd is None:
            raise JournalOwnershipError(
                "A closed journal writer cannot record events.", key="writer_closed")

    def close(self) -> None:
        """Release this process's writer ownership without deleting the lock inode."""
        if self._closed:
            return
        self._closed = True
        fd, self._lock_fd = self._lock_fd, None
        if fd is None:
            return
        try:
            _unlock(fd)
        finally:
            os.close(fd)

    def __enter__(self) -> "JournalWriter":
        self._require_ownership()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def __del__(self) -> None:
        # Normal callers should use close()/a context manager.  This fallback
        # avoids retaining authority solely because a short-lived writer was
        # garbage-collected.  The OS also releases flock on process crash.
        try:
            self.close()
        except Exception:
            pass

    def _load_existing(self) -> None:
        events, tail = read_journal_lines(self.paths.journal_file)
        for event in events:
            self._absorb(event)
        if tail is not None:
            self._quarantine_tail(tail)
            self._atomic_rewrite(events)

    def _absorb(self, event: Mapping[str, Any]) -> None:
        key = content_key(event)
        self._producer_seen[event["producer_event_id"]] = key
        self._event_ids_seen[event["event_id"]] = key
        self._last_digest = event["digest"]
        self._next_seq = event["seq"] + 1

    def _atomic_rewrite(self, events: list[dict[str, Any]]) -> None:
        tmp = self.paths.journal_file.with_name(self.paths.journal_file.name + ".rewrite.tmp")
        with open(tmp, "wb") as handle:
            for event in events:
                handle.write(_canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(self.paths.journal_file))

    def _quarantine_tail(self, tail: bytes) -> None:
        dest = _unique_path(self.paths.quarantine_dir / "truncated_tail.bin")
        dest.write_bytes(tail)
        dest.with_suffix(dest.suffix + ".reason.txt").write_text(
            "truncated_last_line", encoding="utf-8")

    def _quarantine_file(self, path: Path, *, reason: str) -> None:
        dest = _unique_path(self.paths.quarantine_dir / path.name)
        os.replace(str(path), str(dest))
        dest.with_suffix(dest.suffix + ".reason.txt").write_text(reason, encoding="utf-8")

    def _append_journal_line(self, event: Mapping[str, Any]) -> None:
        line = _canonical_bytes(dict(event)) + b"\n"
        with open(self.paths.journal_file, "ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def _finalize(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        finalized = dict(envelope)
        finalized.setdefault("usage", {"status": "unknown"})
        finalized["seq"] = self._next_seq
        finalized["recorded_at"] = self.clock()
        finalized["prev_digest"] = self._last_digest
        body = {k: v for k, v in finalized.items() if k != "digest"}
        finalized["digest"] = "sha256:" + _sha256_hex(_canonical_bytes(body))
        validate_event_envelope(finalized)
        return finalized

    def consume_one(self, ready_path: Path) -> str:
        """Process a single ready file. Returns accepted|duplicate|conflict|quarantined."""
        self._require_ownership()
        try:
            raw = ready_path.read_bytes()
            envelope = json.loads(raw.decode("utf-8"))
            _validate_producer_envelope(envelope, self.paths.run_id)
        except Exception as exc:
            self._quarantine_file(ready_path, reason=f"malformed_ready: {exc}")
            return "quarantined"

        key = content_key(envelope)
        pid, eid = envelope["producer_event_id"], envelope["event_id"]
        prior = self._producer_seen.get(pid, self._event_ids_seen.get(eid))
        if prior is not None:
            if prior == key:
                ready_path.unlink()
                return "duplicate"
            self._quarantine_file(ready_path, reason="idempotency_conflict")
            return "conflict"

        finalized = self._finalize(envelope)
        self._append_journal_line(finalized)
        self._producer_seen[pid] = key
        self._event_ids_seen[eid] = key
        self._last_digest = finalized["digest"]
        self._next_seq += 1
        ready_path.unlink()
        return "accepted"

    def consume_ready(self) -> dict[str, int]:
        """Process every file currently in inbox/ready in deterministic order.

        Ordering is by (submission time, filename), both read from the name
        itself.  :func:`submit_event` stamps the submission time into the ready
        filename, so the order follows the order producers actually submitted
        -- which the reducer needs, since a run cannot be recorded as succeeded
        before the worker it waited on is recorded as passed -- while remaining
        a function of the ready set and nothing else.  Re-running consumption
        over an unchanged set therefore assigns the same seq every time, which
        is what replay depends on.

        Modification time is not used for a file that carries a stamp.  It was,
        and it made ordering depend on wall-clock: filesystem timestamp
        granularity decides which submissions collide, that varies per run, and
        two runs over an identically submitted set could disagree.  A file left
        in ready by an older version has no stamp, so it falls back to
        ``st_mtime_ns``; both are nanoseconds since the epoch and sort together.
        """
        self._require_ownership()
        counts = {"accepted": 0, "duplicate": 0, "conflict": 0, "quarantined": 0}
        entries = []
        for name in os.listdir(self.paths.ready):
            path = self.paths.ready / name
            submitted_at = _submitted_at(path)
            if submitted_at is None:
                try:
                    submitted_at = path.stat().st_mtime_ns
                except OSError:
                    continue
            entries.append((submitted_at, name, path))
        entries.sort(key=lambda item: (item[0], item[1]))
        for _, _, ready_path in entries:
            counts[self.consume_one(ready_path)] += 1
        return counts

    @property
    def last_digest(self) -> str:
        return self._last_digest

    @property
    def next_seq(self) -> int:
        return self._next_seq
