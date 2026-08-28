#!/usr/bin/env python3
"""Exercise one platform installer in an isolated temporary home."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(kind: str) -> None:
    if kind == "sh" and os.name == "nt":
        # Git Bash rewrites HOME to its profile even when a subprocess passes
        # a temporary Windows HOME. The same test runs on the macOS CI job.
        print("installer temp-home test deferred: POSIX shell requires POSIX CI")
        return
    with tempfile.TemporaryDirectory(prefix="graphori-installer-") as directory:
        home = Path(directory)
        env = dict(os.environ)
        env["HOME"] = str(home)
        # An explicit empty value prevents a user-level override from changing
        # the fallback location under test.
        env["GRAPHORI_CODEX_SKILLS_DIR"] = ""
        if kind == "powershell":
            command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "scripts" / "install_skill.ps1"), "-Target", "both"]
            codex = home / ".agents" / "skills" / "graphori"
            claude = home / ".claude" / "skills" / "graphori"
        else:
            # A relative script path works in both Git Bash on Windows and POSIX shells.
            command = ["bash", "scripts/install_skill.sh", "--target", "both"]
            if os.name == "nt":
                # Git Bash needs its POSIX spelling for a Windows temporary HOME.
                windows_home = home.as_posix()
                env["HOME"] = "/" + windows_home[0].lower() + windows_home[2:]
            codex = home / ".agents" / "skills" / "graphori"
            claude = home / ".claude" / "skills" / "graphori"
        result = subprocess.run(command, check=False, env=env, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        if kind == "sh" and os.name == "nt":
            check = subprocess.run(["bash", "-c", "test -f \"$HOME/.agents/skills/graphori/SKILL.md\" && test -f \"$HOME/.claude/skills/graphori/SKILL.md\""], env=env)
            assert check.returncode == 0, env["HOME"]
        else:
            for destination in (codex, claude):
                assert (destination / "SKILL.md").is_file(), destination
                assert (destination / "agents" / "openai.yaml").is_file(), destination
        sentinel = home / ".agents" / "skills" / "other-skill" / "SKILL.md"
        if kind == "sh" and os.name == "nt":
            subprocess.run(["bash", "-c", "mkdir -p \"$HOME/.agents/skills/other-skill\"; printf keep > \"$HOME/.agents/skills/other-skill/SKILL.md\"; printf changed > \"$HOME/.agents/skills/graphori/SKILL.md\""], env=env, check=True)
        else:
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text("keep", encoding="utf-8")
            (codex / "SKILL.md").write_text("changed", encoding="utf-8")
        failed = subprocess.run(command, check=False, env=env, cwd=ROOT, capture_output=True, text=True)
        assert failed.returncode != 0, failed.stdout + failed.stderr
        if kind == "powershell":
            force_command = command + ["-Force"]
        else:
            force_command = command + ["--force"]
        forced = subprocess.run(force_command, check=False, env=env, cwd=ROOT, capture_output=True, text=True)
        if forced.returncode:
            raise RuntimeError(forced.stdout + forced.stderr)
        if kind == "sh" and os.name == "nt":
            preserved = subprocess.run(["bash", "-c", "test \"$(cat \"$HOME/.agents/skills/other-skill/SKILL.md\")\" = keep"], env=env)
            assert preserved.returncode == 0
            backups = subprocess.run(["bash", "-c", "find \"$HOME/.agents/skills\" -maxdepth 1 -type d -name 'graphori.backup-*' | grep ."], env=env, capture_output=True, text=True)
            assert backups.returncode == 0
        else:
            assert sentinel.read_text(encoding="utf-8") == "keep"
            backups = list(codex.parent.glob("graphori.backup-*"))
        assert backups, "force install did not leave a backup"
        if kind == "powershell":
            dashboard_command = command + ["-Skill", "graphori-dashboard"]
        else:
            dashboard_command = command + ["--skill", "graphori-dashboard"]
        dashboard = subprocess.run(
            dashboard_command, check=False, env=env, cwd=ROOT,
            capture_output=True, text=True,
        )
        if dashboard.returncode:
            raise RuntimeError(dashboard.stdout + dashboard.stderr)
        if not (kind == "sh" and os.name == "nt"):
            for parent in (codex.parent, claude.parent):
                destination = parent / "graphori-dashboard"
                assert (destination / "SKILL.md").is_file(), destination
                assert (destination / "agents" / "openai.yaml").is_file(), destination
    print(f"installer temp-home test passed: {kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("powershell", "sh"), required=True)
    args = parser.parse_args(argv)
    run(args.kind)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
