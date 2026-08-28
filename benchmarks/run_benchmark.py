#!/usr/bin/env python3
"""Record one explicit benchmark arm without inventing any result."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("direct", "v1-style", "graphori-v2"), required=True)
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("an explicit command after -- is required; no result was recorded")
    started = datetime.now(timezone.utc)
    result = subprocess.run(command, text=False, capture_output=True, check=False)
    finished = datetime.now(timezone.utc)
    if args.repetition < 1:
        parser.error("--repetition must be positive")
    record = {"schema_version": 1, "run_id": f"{args.provider}-{args.arm}-{started.strftime('%Y%m%dT%H%M%SZ')}", "arm": args.arm, "provider": args.provider, "repetition": args.repetition, "task_id": args.task_id, "started_at": started.isoformat(), "finished_at": finished.isoformat(), "command": command, "outcome": "succeeded" if result.returncode == 0 else "failed", "usage": {"ai_sessions": None, "total_input_tokens": None, "cached_input_tokens": None, "fresh_input_tokens": None, "output_tokens": None, "cost_usd": None}, "quality": {"hidden_tests_passed": None, "hidden_tests_total": None, "ttur_seconds": None, "rework_count": None, "scope_violations": None}, "evidence": {"exit_code": result.returncode, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8", newline="\n") as file: file.write(json.dumps(record, sort_keys=True) + "\n")
    return result.returncode
if __name__ == "__main__": raise SystemExit(main())
