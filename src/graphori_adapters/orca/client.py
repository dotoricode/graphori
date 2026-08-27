"""Version-matched public Orca CLI client."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .adapter import CliResponse


def resolve_orca_executable(
        explicit: Sequence[str] | None = None,
        *, environment: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Resolve the Orca executable once without silent fallback."""

    if explicit is not None:
        result = tuple(explicit)
    else:
        env = environment or os.environ
        configured = env.get("ORCA_CLI_COMMAND", "").strip()
        if configured:
            result = tuple(shlex.split(configured))
        elif env.get("ORCA_DEV_REPO_ROOT"):
            result = ("orca-dev",)
        elif os.name != "nt" and os.uname().sysname == "Linux":
            result = ("orca-ide",)
        else:
            result = ("orca",)
    if not result or any(not isinstance(item, str) or not item for item in result):
        raise ValueError("Orca executable must contain explicit argv entries")
    return result


class OrcaClient:
    """Small command interface; orchestration semantics stay in the adapter."""

    def __init__(
            self, executable: Sequence[str], *, timeout: float = 30.0,
            process_env: Mapping[str, str] | None = None,
            cwd: os.PathLike[str] | str | None = None) -> None:
        self.executable = tuple(executable)
        self.timeout = timeout
        self.process_env = dict(process_env or {})
        self.cwd = Path(cwd).resolve() if cwd is not None else None

    def call(self, args: Sequence[str], *, timeout: float | None = None) -> CliResponse:
        argv = (*self.executable, *args)
        env = dict(os.environ)
        env.update(self.process_env)
        try:
            completed = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding="utf-8", errors="replace", shell=False,
                timeout=timeout or self.timeout, env=env,
                cwd=str(self.cwd) if self.cwd is not None else None,
            )
            return CliResponse(
                argv, completed.returncode, completed.stdout, completed.stderr,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CliResponse(argv, -1, "", "", type(exc).__name__)

    def json(self, args: Sequence[str], *, timeout: float | None = None) -> tuple[Any | None, CliResponse]:
        response = self.call(args, timeout=timeout)
        if not response.ok:
            try:
                return json.loads(response.stdout), response
            except (TypeError, ValueError):
                return None, response
        try:
            return json.loads(response.stdout), response
        except (TypeError, ValueError):
            return None, CliResponse(
                response.argv, response.returncode, response.stdout,
                response.stderr, "malformed_json",
            )

    def guide(self, skill: str) -> tuple[str | None, CliResponse]:
        response = self.call(("skills", "get", skill))
        return (response.stdout if response.ok else None), response

    def status(self):
        return self.json(("status", "--json"))

    def help(self, command: str):
        return self.call(("orchestration", command, "--help"))

    def terminal_help(self, command: str):
        return self.call(("terminal", command, "--help"))

    def run_list(self):
        return self.json(("orchestration", "run-list", "--json"))

    def run_create(self, objective: str):
        return self.json((
            "orchestration", "run-create", "--objective", objective, "--json",
        ))

    def task_list(self, run_id: str):
        return self.json((
            "orchestration", "task-list", "--run", run_id, "--json",
        ))

    def task_create(self, run_id: str, spec: str, title: str):
        return self.json((
            "orchestration", "task-create", "--run", run_id,
            "--spec", spec, "--task-title", title, "--json",
        ))

    def worker_start(self, args: Sequence[str]):
        return self.json(("orchestration", "worker-start", *args, "--json"))

    def terminal_create(self, *, worktree: str, title: str, command: str):
        return self.json((
            "terminal", "create", "--worktree", worktree,
            "--title", title, "--command", command, "--json",
        ))

    def terminal_wait_ready(self, terminal: str, timeout_ms: int):
        return self.json((
            "terminal", "wait", "--terminal", terminal,
            "--for", "tui-idle", "--timeout-ms", str(timeout_ms), "--json",
        ), timeout=max(self.timeout, timeout_ms / 1000 + 5))

    def terminal_close(self, terminal: str):
        return self.json((
            "terminal", "close", "--terminal", terminal, "--json",
        ))

    def check(self, run_id: str, timeout_ms: int):
        return self.json((
            "orchestration", "check", "--run", run_id, "--wait",
            "--types", "worker_done,escalation,question",
            "--timeout-ms", str(timeout_ms), "--json",
        ), timeout=max(self.timeout, timeout_ms / 1000 + 5))

    def acknowledge(self, run_id: str, delivery_id: str):
        return self.json((
            "orchestration", "check", "--run", run_id,
            "--ack", delivery_id, "--json",
        ))

    def worker_release(self, dispatch_id: str):
        return self.json((
            "orchestration", "worker-release", "--dispatch", dispatch_id, "--json",
        ))

    def worker_stop(self, dispatch_id: str):
        return self.json((
            "orchestration", "worker-stop", "--dispatch", dispatch_id, "--json",
        ))

    def worker_show(self, dispatch_id: str):
        return self.json((
            "orchestration", "worker-show", "--dispatch", dispatch_id, "--json",
        ))
