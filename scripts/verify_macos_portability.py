#!/usr/bin/env python3
"""Run the dedicated macOS adapter fixtures and emit contract-shaped evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "process_tree": (
        "test_process_supervisor.TimeoutTreeKillTests."
        "test_timeout_terminates_child_and_grandchild",
    ),
    "path_escape": (
        "test_paths_security.PathSecurityTests.test_relative_traversal_is_rejected",
        "test_paths_security.PathSecurityTests."
        "test_absolute_and_drive_relative_and_unc_escape_is_rejected",
        "test_process_supervisor.ExternalMarkerInvarianceTests."
        "test_marker_outside_workspace_is_unchanged_after_rejected_escape_and_timeout_kill",
    ),
    "symlink": (
        "test_paths_security.PathSecurityTests.test_posix_symlink_escape_is_rejected",
    ),
    "case_collision": (
        "test_paths_security.PathSecurityTests.test_case_collision_ambiguity_is_rejected",
        "test_process_supervisor.ArgvAndCwdSafetyTests.test_case_collision_cwd_is_rejected",
    ),
    "jsonl_tmp_ready": (
        "test_journal_ordering",
        "test_journal_concurrency",
    ),
    "replay_idempotency": (
        "test_journal_replay",
        "test_journal_idempotency",
    ),
}


def run_fixture(name: str, tests: tuple[str, ...]) -> dict[str, str]:
    command = [sys.executable, "-m", "unittest", *tests]
    environment = dict(os.environ)
    roots = [str(ROOT / "tests"), str(ROOT / "src")]
    if environment.get("PYTHONPATH"):
        roots.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(roots)
    result = subprocess.run(
        command, cwd=ROOT, env=environment, text=True, capture_output=True,
    )
    evidence_text = (result.stdout + "\n" + result.stderr).strip()
    evidence = evidence_text.encode("utf-8")
    passed = result.returncode == 0 and "skipped=" not in evidence_text
    return {
        "platform": "macos",
        "fixture": name,
        "verdict": "pass" if passed else "fail",
        "evidence_id": f"macos:{name}",
        "command": " ".join(command),
        "host": platform.platform(),
        "hash": "sha256:" + hashlib.sha256(evidence).hexdigest(),
        "evidence": evidence_text,
    }


def verify() -> list[dict[str, str]]:
    if sys.platform != "darwin":
        raise RuntimeError("the macOS portability fixture requires a macOS host")
    records = [run_fixture(name, tests) for name, tests in FIXTURES.items()]
    failed = [record["fixture"] for record in records if record["verdict"] != "pass"]
    if failed:
        raise RuntimeError("portability fixture failed: " + ", ".join(failed))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        records = verify()
        text = json.dumps(records, indent=2, sort_keys=True) + "\n"
        if args.output:
            output = args.output.resolve()
            if output.exists():
                raise ValueError(f"output already exists: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"MACOS PORTABILITY VERIFICATION: FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
