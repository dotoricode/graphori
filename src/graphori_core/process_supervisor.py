"""Generic, non-interactive process supervisor.

This is the ``ProcessSupervisor`` port from
:doc:`/architecture/GRAPHORI_ARCHITECTURE` and the process rules from
:doc:`/architecture/PORTABILITY_CONTRACT`: explicit argv (never a shell
string), a workspace-confined cwd, an env allowlist that refuses
secret-looking names, bounded stdout/stderr capture, and -- on timeout --
termination of the whole descendant tree, not just the direct child.

Windows uses a Job Object (``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``) so the
whole tree dies even if a grandchild detaches from its parent. If the Job
Object cannot be created or assigned, this honestly records that fact
(``tree_kill_method``/``tree_kill_evidence``) and falls back to
``taskkill /T /F`` instead of silently claiming success. POSIX uses a new
process group (``os.setsid``/``start_new_session``) and ``killpg``; that
code path is platform-branched and exercised by unit tests, but this
repository has only ever executed it on a Windows host, so it must never be
reported as a verified macOS PASS -- see ``docs/architecture/PORTABILITY_CONTRACT.md``
section 4.

PTY, ConPTY, tmux, and GUI/browser automation are explicitly out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import signal
import subprocess
import sys
import threading
from typing import Any, Mapping, Sequence

from .paths import PathSecurityError, resolve_run_root, safe_join

WINDOWS = sys.platform == "win32"

if WINDOWS:
    try:
        from . import _win_job
    except Exception:  # pragma: no cover - ctypes should always be present
        _win_job = None  # type: ignore[assignment]
else:
    _win_job = None  # type: ignore[assignment]


class ProcessSupervisorError(ValueError):
    """Raised for invalid supervisor input (argv shape, bad limits, ...)."""


# Minimal set of variables most non-interactive tooling needs to run at all.
# Anything else must be requested explicitly via ``env`` and still passes
# through the secret-name filter below.
DEFAULT_ENV_ALLOWLIST = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "TEMP", "TMP",
    "TMPDIR", "HOME", "LANG", "LC_ALL", "SHELL", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "OS", "WINDIR", "PYTHONDONTWRITEBYTECODE",
})

# Defense in depth: even a name explicitly present in an allowlist is
# dropped if it looks like a secret, so a caller cannot leak credentials by
# widening the allowlist. This is a name-based heuristic, not a value scan.
_SECRET_NAME_PATTERN = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|API[_-]?KEY|PRIVATE[_-]?KEY|"
    r"ACCESS[_-]?KEY|AUTH|CLIENT[_-]?SECRET)",
    re.IGNORECASE,
)


def build_child_env(*, base_env: Mapping[str, str], extra_env: Mapping[str, str] | None = None,
                     allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST) -> tuple[dict[str, str], tuple[str, ...]]:
    """Build the child's environment from an allowlist, honestly reporting drops.

    Returns ``(child_env, dropped_keys)``. ``dropped_keys`` covers both
    non-allowlisted names and allowlisted-but-secret-looking names, sorted
    for deterministic evidence.
    """
    normalized_allow = {name.upper() for name in allowlist}
    merged: dict[str, str] = dict(base_env)
    if extra_env:
        merged.update(extra_env)
    child: dict[str, str] = {}
    dropped: list[str] = []
    for key, value in merged.items():
        if key.upper() not in normalized_allow:
            dropped.append(key)
            continue
        if _SECRET_NAME_PATTERN.search(key):
            dropped.append(key)
            continue
        child[key] = value
    return child, tuple(sorted(dropped))


def resolve_workspace_path(workspace_root: os.PathLike | str, relative_path: os.PathLike | str) -> Path:
    """Resolve ``relative_path`` (e.g. a requested cwd) inside the workspace root.

    Only relative paths are accepted; absolute, drive-relative, UNC, ``..``
    traversal, symlink/junction escapes, and case-collision ambiguity are all
    rejected by reusing :func:`graphori_core.paths.safe_join`.
    """
    root = resolve_run_root(workspace_root)
    text = str(relative_path).strip()
    if text in ("", "."):
        return root
    candidate = Path(text)
    if candidate.is_absolute():
        raise PathSecurityError(f"path must be relative to the workspace root: {relative_path!r}")
    return safe_join(root, *candidate.parts)


def _validate_argv(argv: Any) -> list[str]:
    if isinstance(argv, (str, bytes)):
        raise ProcessSupervisorError(
            "argv must be an explicit list of strings, not a shell command string"
        )
    if not isinstance(argv, Sequence):
        raise ProcessSupervisorError(f"argv must be a sequence of strings: {argv!r}")
    items = list(argv)
    if not items:
        raise ProcessSupervisorError("argv must contain at least the executable")
    for item in items:
        if not isinstance(item, str) or not item:
            raise ProcessSupervisorError(f"every argv entry must be a non-empty string: {item!r}")
    return items


@dataclass(frozen=True)
class ProcessLimits:
    max_stdout_bytes: int = 1_000_000
    max_stderr_bytes: int = 1_000_000
    max_lines: int = 20_000
    timeout_seconds: float | None = None
    grace_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.max_stdout_bytes < 0 or self.max_stderr_bytes < 0:
            raise ProcessSupervisorError("byte limits must be non-negative")
        if self.max_lines < 0:
            raise ProcessSupervisorError("max_lines must be non-negative")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ProcessSupervisorError("timeout_seconds must be positive when set")
        if self.grace_seconds < 0:
            raise ProcessSupervisorError("grace_seconds must be non-negative")


@dataclass(frozen=True)
class ProcessResult:
    pid: int
    exit_code: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_total_bytes: int
    stderr_total_bytes: int
    started_at: float
    finished_at: float
    first_stdout_at: float | None
    last_stdout_at: float | None
    tree_kill_used: bool
    tree_kill_method: str
    tree_kill_evidence: str
    dropped_env_keys: tuple[str, ...] = ()
    cancelled: bool = False

    @property
    def duration_seconds(self) -> float:
        return self.finished_at - self.started_at


@dataclass
class ProcessExecution:
    """Opaque running-process handle owned by :class:`ProcessSupervisor`."""

    process: subprocess.Popen
    stdout_reader: "_BoundedReader"
    stderr_reader: "_BoundedReader"
    limits: ProcessLimits
    started_at: float
    job: Any
    job_evidence: str
    dropped_env_keys: tuple[str, ...]
    cancelled: bool = False
    timed_out: bool = False
    tree_kill_used: bool = False
    tree_kill_method: str = "none"
    tree_kill_evidence: str = ""
    result: ProcessResult | None = None
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class _BoundedReader(threading.Thread):
    """Drain a pipe under a byte/line cap without ever blocking the child.

    Uses chunked ``read`` rather than ``readline`` so a single unbounded line
    cannot exceed the byte cap before it is ever inspected. Once the cap is
    hit, remaining bytes are still read and discarded (never buffered) so the
    child's pipe never backs up and deadlocks the wait.
    """

    CHUNK = 8192

    def __init__(self, stream: Any, max_bytes: int, max_lines: int,
                 monotonic: Any) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.max_bytes = max_bytes
        self.max_lines = max_lines
        self.buffer = bytearray()
        self.truncated = False
        self.total_bytes = 0
        self.total_lines = 0
        self.monotonic = monotonic
        self.first_chunk_at: float | None = None
        self.last_chunk_at: float | None = None

    def run(self) -> None:
        try:
            while True:
                read = getattr(self.stream, "read1", self.stream.read)
                chunk = read(self.CHUNK)
                if not chunk:
                    break
                observed_at = self.monotonic()
                if self.first_chunk_at is None:
                    self.first_chunk_at = observed_at
                self.last_chunk_at = observed_at
                self.total_bytes += len(chunk)
                self.total_lines += chunk.count(b"\n")
                if self.truncated:
                    continue
                if self.total_lines > self.max_lines:
                    self.truncated = True
                    continue
                remaining = self.max_bytes - len(self.buffer)
                if remaining <= 0:
                    self.truncated = True
                    continue
                self.buffer.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        finally:
            try:
                self.stream.close()
            except Exception:
                pass


def _kill_tree_windows(proc: subprocess.Popen, job: Any, job_evidence: str,
                       *, grace: float) -> tuple[int | None, str, str]:
    if job is not None:
        try:
            job.terminate()
            try:
                proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                pass
            return proc.poll(), "job_object", f"job_object_terminate_ok; setup={job_evidence}"
        except Exception as exc:  # pragma: no cover - defensive
            job_evidence = f"{job_evidence}; terminate_failed={exc!r}"
    result = subprocess.run(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
        capture_output=True, text=True,
    )
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
    evidence = (f"job_object_unavailable({job_evidence}); "
                f"taskkill_rc={result.returncode} taskkill_stderr={result.stderr.strip()!r}")
    return proc.poll(), "taskkill_fallback", evidence


def _kill_tree_posix(proc: subprocess.Popen, *, grace: float) -> tuple[int | None, str, str]:
    pid = proc.pid
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError, OSError) as exc:
        proc.kill()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        return proc.poll(), "kill_fallback_no_group", f"getpgid_failed: {exc!r}"
    try:
        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait(timeout=grace)
        return proc.poll(), "process_group", (
            "posix_process_group_signal; code path is platform-branched but has "
            "only been exercised on a Windows host in this repository -- do not "
            "cite this as a verified macOS PASS without running the same fixture "
            "on a real macOS/CI host (see PORTABILITY_CONTRACT.md section 4)"
        )
    except (ProcessLookupError, PermissionError, OSError) as exc:
        proc.kill()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        return proc.poll(), "kill_fallback_group_signal_failed", f"killpg_failed: {exc!r}"


@dataclass
class ProcessSupervisor:
    """Starts, bounds, and tears down one non-interactive child process tree."""

    clock: Any = None

    def __post_init__(self) -> None:
        if self.clock is None:
            from .clock import SystemClock
            self.clock = SystemClock()

    def start(self, argv: Sequence[str], *, workspace_root: os.PathLike | str,
              cwd: os.PathLike | str = ".", env: Mapping[str, str] | None = None,
              env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
              limits: ProcessLimits = ProcessLimits()) -> ProcessExecution:
        argv = _validate_argv(argv)
        resolved_cwd = resolve_workspace_path(workspace_root, cwd)
        child_env, dropped = build_child_env(base_env=os.environ, extra_env=env, allowlist=env_allowlist)

        job = None
        job_evidence = "not_windows"
        popen_kwargs: dict[str, Any] = {}
        if WINDOWS:
            if _win_job is not None:
                try:
                    job = _win_job.WindowsJob()
                    job_evidence = "job_object_created"
                except Exception as exc:
                    job = None
                    job_evidence = f"job_object_create_failed: {exc!r}"
            else:
                job_evidence = "win_job_module_unavailable"
        else:
            popen_kwargs["start_new_session"] = True

        started_at = self.clock.monotonic()
        proc = subprocess.Popen(
            argv, cwd=str(resolved_cwd), env=child_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **popen_kwargs,
        )
        if WINDOWS and job is not None:
            try:
                job.assign(proc.pid)
            except Exception as exc:
                job_evidence = f"{job_evidence}; assign_failed={exc!r}"
                job.close()
                job = None

        out_reader = _BoundedReader(
            proc.stdout, limits.max_stdout_bytes, limits.max_lines,
            self.clock.monotonic,
        )
        err_reader = _BoundedReader(
            proc.stderr, limits.max_stderr_bytes, limits.max_lines,
            self.clock.monotonic,
        )
        out_reader.start()
        err_reader.start()

        return ProcessExecution(
            process=proc,
            stdout_reader=out_reader,
            stderr_reader=err_reader,
            limits=limits,
            started_at=started_at,
            job=job,
            job_evidence=job_evidence,
            dropped_env_keys=dropped,
            tree_kill_evidence=job_evidence,
        )

    def _terminate(self, execution: ProcessExecution, *, cancelled: bool) -> bool:
        with execution.lock:
            if not cancelled:
                execution.timed_out = True
            if execution.process.poll() is not None:
                return False
            execution.cancelled = execution.cancelled or cancelled
            execution.tree_kill_used = True
            if WINDOWS:
                code, method, evidence = _kill_tree_windows(
                    execution.process, execution.job, execution.job_evidence,
                    grace=execution.limits.grace_seconds,
                )
            else:
                code, method, evidence = _kill_tree_posix(
                    execution.process, grace=execution.limits.grace_seconds,
                )
            execution.tree_kill_method = method
            execution.tree_kill_evidence = evidence
            return code is not None

    def cancel(self, execution: ProcessExecution) -> bool:
        """Terminate a running process tree, returning whether work was stopped."""
        return self._terminate(execution, cancelled=True)

    def collect(self, execution: ProcessExecution) -> ProcessResult:
        with execution.lock:
            if execution.result is not None:
                return execution.result

        try:
            exit_code: int | None = execution.process.wait(
                timeout=execution.limits.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            self._terminate(execution, cancelled=False)
            exit_code = execution.process.poll()
        finally:
            if WINDOWS and execution.job is not None:
                # Kill-on-close reaps any leftover descendant even on a
                # normal exit, so the adapter never leaves stray children.
                execution.job.close()
                execution.job = None

        execution.stdout_reader.join(
            timeout=max(execution.limits.grace_seconds, 1.0) + 5,
        )
        execution.stderr_reader.join(
            timeout=max(execution.limits.grace_seconds, 1.0) + 5,
        )
        finished_at = self.clock.monotonic()

        result = ProcessResult(
            pid=execution.process.pid,
            exit_code=exit_code,
            timed_out=execution.timed_out,
            stdout=bytes(execution.stdout_reader.buffer),
            stderr=bytes(execution.stderr_reader.buffer),
            stdout_truncated=execution.stdout_reader.truncated,
            stderr_truncated=execution.stderr_reader.truncated,
            stdout_total_bytes=execution.stdout_reader.total_bytes,
            stderr_total_bytes=execution.stderr_reader.total_bytes,
            started_at=execution.started_at,
            finished_at=finished_at,
            first_stdout_at=execution.stdout_reader.first_chunk_at,
            last_stdout_at=execution.stdout_reader.last_chunk_at,
            tree_kill_used=execution.tree_kill_used,
            tree_kill_method=execution.tree_kill_method,
            tree_kill_evidence=execution.tree_kill_evidence,
            dropped_env_keys=execution.dropped_env_keys,
            cancelled=execution.cancelled,
        )
        with execution.lock:
            if execution.result is None:
                execution.result = result
            return execution.result

    def run(self, argv: Sequence[str], *, workspace_root: os.PathLike | str,
            cwd: os.PathLike | str = ".", env: Mapping[str, str] | None = None,
            env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
            limits: ProcessLimits = ProcessLimits()) -> ProcessResult:
        execution = self.start(
            argv, workspace_root=workspace_root, cwd=cwd, env=env,
            env_allowlist=env_allowlist, limits=limits,
        )
        return self.collect(execution)
