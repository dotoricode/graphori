"""Generate sanitized, content-addressed CI evidence manifests.

Only stable labels and relative commands are recorded. Host paths, environment
values, credentials, and runner metadata are deliberately excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as platform_module
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = {
    "portable": ["python", "-m", "unittest", "tests.test_core"],
    "core": ["python", "-m", "unittest", "tests.test_core"],
    "adapter": ["python", "-m", "unittest", "tests.test_orca_adapter"],
    "dashboard": ["python", "-m", "unittest", "tests.test_dashboard", "tests.test_dashboard_ui"],
}


def _safe_command(argv: list[str]) -> str:
    # Do not serialize a runner-specific executable path or shell expansion.
    return " ".join("python" if i == 0 else item for i, item in enumerate(argv))


def _process_supervisor_fixture() -> tuple[str, str]:
    from graphori_core.process_supervisor import ProcessLimits, ProcessSupervisor

    result = ProcessSupervisor().run(
        [sys.executable, "-c", "import time; time.sleep(0.05)"],
        workspace_root=Path.cwd(),
        limits=ProcessLimits(timeout_seconds=2, grace_seconds=1),
    )
    return ("pass" if result.exit_code == 0 and not result.timed_out else "fail", "posix_or_windows_process_fixture")


def run(platform_name: str, output: Path) -> dict:
    records = []
    for fixture, argv in FIXTURES.items():
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = "src"
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=120,
                                   check=False, env=child_env)
        verdict = "pass" if completed.returncode == 0 else "fail"
        command = _safe_command(argv)
        identity = f"{platform_name}|{fixture}|{verdict}|{command}"
        records.append({
            "platform": platform_name,
            "fixture": fixture,
            "verdict": verdict,
            "evidence_id": "ev_" + hashlib.sha256(identity.encode()).hexdigest()[:16],
            "command": command,
            "scope": "runner_actual",
        })
    verdict, fixture_detail = _process_supervisor_fixture()
    identity = f"{platform_name}|process_supervisor|{verdict}|{fixture_detail}"
    records.append({
        "platform": platform_name,
        "fixture": "process_supervisor",
        "verdict": verdict,
        "evidence_id": "ev_" + hashlib.sha256(identity.encode()).hexdigest()[:16],
        "command": "python ProcessSupervisor finite child fixture",
        "scope": "runner_actual",
    })
    manifest = {"schema_version": 1, "platform": platform_name, "records": records,
                "scope": "runner_actual", "generated_by": "scripts/generate_ci_evidence.py"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = output.with_suffix(".md")
    lines = ["# I08 CI 증거", "", "실행한 runner의 결과만 기록했습니다. 실패는 PASS로 바꾸지 않았습니다.", "",
             "| OS | fixture | verdict | evidence_id |", "|---|---|---|---|"]
    lines += [f"| {r['platform']} | {r['fixture']} | {r['verdict']} | {r['evidence_id']} |" for r in records]
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("windows", "macos"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = run(args.platform, args.output)
    print(json.dumps({"platform": manifest["platform"], "records": len(manifest["records"]),
                      "verdicts": [r["verdict"] for r in manifest["records"]]}))
    return 0 if all(r["verdict"] == "pass" for r in manifest["records"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
