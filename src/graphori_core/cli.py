"""Generic terminal adapter CLI: ``run``, ``status``, ``replay``.

This is the Orca-independent front door described in
``docs/architecture/PORTABILITY_CONTRACT.md``: everything it does also works
with no Orca connection at all. ``run`` dispatches one non-interactive
attempt through :class:`~graphori_core.agent_runner.AgentRunner`, recording
the canonical events produced so far to the single-writer JSONL journal. A
successful child process stops at ``awaiting_verification``; only a later
verifier or gate may produce verified completion. ``status`` and ``replay`` only ever read
that journal back -- they never depend on any state ``run`` held in memory,
so they work from a separate process invocation.

The adapter's own graph is intentionally the smallest one the event
protocol allows: one ``worker`` node. Topology is compiler-owned, not
journal-stored (mirrors ``EVENT_PROTOCOL.md`` section 4.2), so ``status``
and ``replay`` rebuild that same one-node graph deterministically from
``run_id``/``task_id`` instead of reading it back from events.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

from .agent_runner import AgentRunner
from .clock import SystemClock
from .compiler import StateTransitionError
from .journal import (
    JournalOwnershipError, JournalWriter, ensure_run_dirs, read_journal_lines,
    replay_journal, submit_event,
)
from .models import Attempt, Node, NodeKind, NodeState, Role, Run, Task
from .paths import PathSecurityError
from .process_supervisor import ProcessLimits, ProcessSupervisor, ProcessSupervisorError
from .reducer import StateReducer

_ACTOR_IDS = {
    "router": "role_cli_router",
    "scheduler": "role_cli_scheduler",
    "worker": "role_worker",
}


def _default_task_id(run_id: str) -> str:
    return f"task_{run_id}"


def _build_single_worker_run(run_id: str, task_id: str) -> tuple[Task, Run]:
    """The adapter's minimal, deterministic topology: one worker node.

    ``status``/``replay`` call this with the same ``run_id``/``task_id`` that
    ``run`` used so a fresh reducer reproduces the identical graph shape
    before applying the journaled events on top of it.
    """
    task = Task(task_id, "generic terminal adapter attempt", run_id=run_id, graph_version=1)
    run = Run(run_id, graph_version=1)
    role = Role("role_worker", NodeKind.WORKER, "generic-worker")
    run.graph.add_node(Node("worker", NodeKind.WORKER, "Worker", role=role))
    return task, run


def _build_envelope(*, event_type: str, run_id: str, task_id: str, seq_hint: int,
                    occurred_at: str, actor_role: str = "router",
                    entity_extra: dict[str, Any] | None = None,
                    payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": f"evt_{uuid.uuid4().hex}",
        "producer_event_id": f"producer:cli:{run_id}:{seq_hint}",
        "run_id": run_id,
        "graph_version": 1,
        "occurred_at": occurred_at,
        "actor": {"role": actor_role,
                  "role_id": _ACTOR_IDS.get(actor_role, f"role_cli_{actor_role}")},
        "type": event_type,
        "entity": {"task_id": task_id, **(entity_extra or {})},
        "payload": dict(payload or {}),
    }


def _emit(paths, writer: JournalWriter, reducer: StateReducer, *, event_type: str,
          run_id: str, task_id: str, seq_hint: int, clock, actor_role="router",
          entity_extra=None, payload=None) -> dict[str, Any]:
    """Submit one event through the real tmp->ready->journal path, then
    project it through the in-process reducer so ``run`` can make
    subsequent decisions (e.g. did the node reach PASSED?)."""
    envelope = _build_envelope(
        event_type=event_type, run_id=run_id, task_id=task_id, seq_hint=seq_hint,
        occurred_at=clock.now_utc(), actor_role=actor_role,
        entity_extra=entity_extra, payload=payload,
    )
    ready_path = submit_event(paths, envelope, local_seq=seq_hint)
    outcome = writer.consume_one(ready_path)
    if outcome != "accepted":
        raise StateTransitionError(f"event {event_type} was not accepted by the journal: {outcome}")
    events, _tail = read_journal_lines(paths.journal_file)
    finalized = events[-1]
    reducer.apply(finalized)
    return finalized


def _parse_env_pairs(pairs: Sequence[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise ProcessSupervisorError(f"--env expects KEY=VALUE, got: {item!r}")
        key, _, value = item.partition("=")
        if not key:
            raise ProcessSupervisorError(f"--env key must be non-empty: {item!r}")
        env[key] = value
    return env


def cmd_run(args: argparse.Namespace) -> int:
    if not args.argv:
        print("error: no command given -- pass it after '--', e.g. `run -- python -c pass`", file=sys.stderr)
        return 2
    argv = args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv

    task_id = args.task_id or _default_task_id(args.run_id)
    clock = SystemClock()
    paths = ensure_run_dirs(args.root, args.run_id)
    writer = JournalWriter(paths, clock=clock.now_utc)
    task, run = _build_single_worker_run(args.run_id, task_id)
    reducer = StateReducer(task, run)

    seq = 1
    _emit(paths, writer, reducer, event_type="run_created", run_id=args.run_id, task_id=task_id,
          seq_hint=seq, clock=clock); seq += 1
    _emit(paths, writer, reducer, event_type="graph_published", run_id=args.run_id, task_id=task_id,
          seq_hint=seq, clock=clock); seq += 1

    def node_event(status: str, *, actor_role: str):
        nonlocal seq
        _emit(paths, writer, reducer, event_type="node_status_changed", run_id=args.run_id,
              task_id=task_id, seq_hint=seq, clock=clock, actor_role=actor_role,
              entity_extra={"node_id": "worker"}, payload={"status": status})
        seq += 1

    node_event(NodeState.READY.value, actor_role="scheduler")

    attempt_id = f"attempt_{uuid.uuid4().hex[:12]}"
    attempt = Attempt(attempt_id, task_id, Role("role_worker", NodeKind.WORKER, "generic-worker"))

    try:
        env = _parse_env_pairs(args.env)
    except ProcessSupervisorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        writer.close()
        return 2

    _emit(paths, writer, reducer, event_type="attempt_dispatched", run_id=args.run_id, task_id=task_id,
          seq_hint=seq, clock=clock, actor_role="scheduler",
          entity_extra={"node_id": "worker", "attempt_id": attempt_id},
          payload={"argv": argv, "cwd": args.cwd}); seq += 1
    node_event(NodeState.ASSIGNED.value, actor_role="scheduler")
    node_event(NodeState.RUNNING.value, actor_role="worker")

    limits = ProcessLimits(
        max_stdout_bytes=args.max_stdout_bytes, max_stderr_bytes=args.max_stderr_bytes,
        timeout_seconds=args.timeout, grace_seconds=args.grace,
    )
    supervisor = ProcessSupervisor(clock=clock)
    runner = AgentRunner(supervisor, clock=clock)
    try:
        outcome = runner.run_attempt(
            attempt, argv=argv, workspace_root=args.root, cwd=args.cwd, env=env, limits=limits,
        )
    except ProcessSupervisorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        writer.close()
        return 2

    payload = outcome.worker_finished_payload()
    _emit(paths, writer, reducer, event_type="worker_finished", run_id=args.run_id, task_id=task_id,
          seq_hint=seq, clock=clock, actor_role="worker",
          entity_extra={"node_id": "worker", "attempt_id": attempt_id},
          payload=payload); seq += 1

    succeeded = (not outcome.process.timed_out) and outcome.process.exit_code == 0
    node_event(
        NodeState.AWAITING_VERIFICATION.value if succeeded else NodeState.FAILED.value,
        actor_role="worker",
    )
    terminal_status = None
    if not succeeded:
        terminal_status = "failed"
        _emit(paths, writer, reducer, event_type="run_terminal", run_id=args.run_id,
              task_id=task_id, seq_hint=seq, clock=clock,
              payload={"terminal_status": terminal_status}); seq += 1

    summary = {
        "run_id": args.run_id, "task_id": task_id, "attempt_id": attempt_id,
        "terminal_status": terminal_status,
        "execution_outcome": "succeeded" if succeeded else "failed",
        "exit_code": outcome.process.exit_code,
        "timed_out": outcome.process.timed_out,
        "tree_kill_used": outcome.process.tree_kill_used,
        "tree_kill_method": outcome.process.tree_kill_method,
        "stdout_truncated": outcome.process.stdout_truncated,
        "stderr_truncated": outcome.process.stderr_truncated,
        "dropped_env_keys": list(outcome.process.dropped_env_keys),
        "journal_file": str(paths.journal_file),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    writer.close()
    return 0 if succeeded else 1


def _journal_events(root, run_id: str):
    paths = ensure_run_dirs(root, run_id)
    writer = JournalWriter(paths)  # recovers any truncated tail into quarantine/ first
    writer.close()
    events, digest = replay_journal(paths)
    return paths, events, digest


def cmd_status(args: argparse.Namespace) -> int:
    task_id = args.task_id or _default_task_id(args.run_id)
    paths, events, _digest = _journal_events(args.root, args.run_id)
    task, run = _build_single_worker_run(args.run_id, task_id)
    reducer = StateReducer(task, run)
    for event in events:
        reducer.apply(event)

    node_states = {node_id: node.state.value for node_id, node in run.graph.nodes.items()}
    result = {
        "run_id": args.run_id,
        "task_id": task_id,
        "event_count": len(events),
        "terminal_status": run.terminal_status.value if run.terminal_status else None,
        "node_states": node_states,
        "platform_summary": reducer.platform_summary(),
        "journal_file": str(paths.journal_file),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"run_id: {result['run_id']}")
        print(f"task_id: {result['task_id']}")
        print(f"events: {result['event_count']}")
        print(f"terminal_status: {result['terminal_status']}")
        for node_id, state in node_states.items():
            print(f"node[{node_id}]: {state}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    paths, events, digest = _journal_events(args.root, args.run_id)
    if args.verify:
        _paths2, events2, digest2 = _journal_events(args.root, args.run_id)
        if digest2 != digest or events2 != events:
            print("error: replay is not deterministic -- digest mismatch on second pass", file=sys.stderr)
            return 1

    result = {
        "run_id": args.run_id,
        "event_count": len(events),
        "projection_digest": digest,
        "events": [{"seq": e["seq"], "type": e["type"], "entity": e["entity"]} for e in events],
        "journal_file": str(paths.journal_file),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"run_id: {result['run_id']}")
        print(f"events: {result['event_count']}")
        print(f"projection_digest: {digest}")
        for row in result["events"]:
            print(f"  seq={row['seq']:>4} type={row['type']} entity={row['entity']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphori-cli", description="Graphori generic terminal adapter (no Orca dependency)")
    parser.add_argument("--root", required=True, help="workspace root directory")
    parser.add_argument("--run-id", required=True, help="run identifier")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="dispatch and execute one non-interactive attempt")
    run_p.add_argument("--task-id", default=None)
    run_p.add_argument("--cwd", default=".")
    run_p.add_argument("--timeout", type=float, default=None)
    run_p.add_argument("--grace", type=float, default=3.0)
    run_p.add_argument("--max-stdout-bytes", type=int, default=1_000_000)
    run_p.add_argument("--max-stderr-bytes", type=int, default=1_000_000)
    run_p.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    run_p.add_argument("argv", nargs=argparse.REMAINDER,
                       help="the explicit argv to execute, e.g. -- python -c pass")
    run_p.set_defaults(func=cmd_run)

    status_p = sub.add_parser("status", help="show the current projected run/node status")
    status_p.add_argument("--task-id", default=None)
    status_p.add_argument("--json", action="store_true")
    status_p.set_defaults(func=cmd_status)

    replay_p = sub.add_parser("replay", help="replay the journal and print its digest")
    replay_p.add_argument("--verify", action="store_true",
                          help="replay twice and confirm the digest matches both times")
    replay_p.add_argument("--json", action="store_true")
    replay_p.set_defaults(func=cmd_replay)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (JournalOwnershipError, StateTransitionError, ProcessSupervisorError, PathSecurityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
