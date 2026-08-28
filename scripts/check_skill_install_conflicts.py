#!/usr/bin/env python3
"""Detect Graphori Skills exposed by both a plugin and a standalone copy."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path


PLUGIN_ID = "graphori@graphori"
SKILLS = ("graphori", "graphori-dashboard")


def codex_plugin_enabled(home: Path) -> bool:
    codex_root = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    config = codex_root / "config.toml"
    if not config.is_file():
        return False
    with config.open("rb") as stream:
        data = tomllib.load(stream)
    plugin = data.get("plugins", {}).get(PLUGIN_ID, {})
    return isinstance(plugin, dict) and plugin.get("enabled") is True


def claude_plugin_enabled(home: Path) -> bool:
    settings = home / ".claude" / "settings.json"
    if not settings.is_file():
        return False
    data = json.loads(settings.read_text(encoding="utf-8"))
    enabled = data.get("enabledPlugins", {})
    return isinstance(enabled, dict) and enabled.get(PLUGIN_ID) is True


def standalone_path(home: Path, target: str, skill: str) -> Path:
    if target == "codex":
        root = Path(
            os.environ.get("GRAPHORI_CODEX_SKILLS_DIR", home / ".agents" / "skills")
        )
    else:
        root = home / ".claude" / "skills"
    return root / skill


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when Graphori is exposed by a plugin and standalone Skills."
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument(
        "--target", choices=("codex", "claude", "both"), default="both"
    )
    parser.add_argument(
        "--skill", choices=(*SKILLS, "all"), default="all"
    )
    parser.add_argument(
        "--before-standalone-install",
        action="store_true",
        help="also reject a plugin-only state because the requested copy would conflict",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = ("codex", "claude") if args.target == "both" else (args.target,)
    skills = SKILLS if args.skill == "all" else (args.skill,)
    conflicts: list[str] = []

    try:
        for target in targets:
            plugin_enabled = (
                codex_plugin_enabled(args.home)
                if target == "codex"
                else claude_plugin_enabled(args.home)
            )
            if not plugin_enabled:
                continue
            for skill in skills:
                path = standalone_path(args.home, target, skill)
                if args.before_standalone_install or (path / "SKILL.md").is_file():
                    conflicts.append(f"{target}: {PLUGIN_ID} + {path}")
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"cannot verify Graphori installation state: {error}", file=sys.stderr)
        return 2

    if conflicts:
        print(
            "duplicate Graphori installation: plugin and standalone Skill are both "
            "enabled; choose exactly one installation route.",
            file=sys.stderr,
        )
        for conflict in conflicts:
            print(f"- {conflict}", file=sys.stderr)
        return 1

    print("no duplicate Graphori installation detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
