from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_skill_install_conflicts.py"


def run_checker(
    home: Path, target: str, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--home",
            str(home),
            "--target",
            target,
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


class SkillInstallConflictTests(unittest.TestCase):
    def test_codex_plugin_and_standalone_skill_are_reported_as_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins."graphori@graphori"]\nenabled = true\n',
                encoding="utf-8",
            )
            skill = home / ".agents" / "skills" / "graphori" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: graphori\n---\n", encoding="utf-8")

            result = run_checker(home, "codex")

            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate Graphori installation", result.stderr)
            self.assertIn("plugin and standalone Skill are both enabled", result.stderr)

    def test_claude_plugin_and_standalone_skill_are_reported_as_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            settings = home / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                json.dumps({"enabledPlugins": {"graphori@graphori": True}}),
                encoding="utf-8",
            )
            skill = home / ".claude" / "skills" / "graphori" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: graphori\n---\n", encoding="utf-8")

            result = run_checker(home, "claude")

            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate Graphori installation", result.stderr)

    def test_one_installation_route_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins."graphori@graphori"]\nenabled = true\n',
                encoding="utf-8",
            )

            result = run_checker(home, "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no duplicate Graphori installation", result.stdout)

    def test_standalone_install_is_refused_when_plugin_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins."graphori@graphori"]\nenabled = true\n',
                encoding="utf-8",
            )

            result = run_checker(home, "codex", "--before-standalone-install")

            self.assertEqual(result.returncode, 1)
            self.assertIn("choose exactly one installation route", result.stderr)

    def test_installer_calls_the_conflict_checker_before_copying(self) -> None:
        shell = (ROOT / "scripts" / "install_skill.sh").read_text(encoding="utf-8")
        powershell = (ROOT / "scripts" / "install_skill.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("check_skill_install_conflicts.py", shell)
        self.assertIn("check_skill_install_conflicts.py", powershell)

    def test_shell_installer_does_not_copy_beside_enabled_codex_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins."graphori@graphori"]\nenabled = true\n',
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update({"HOME": str(home), "GRAPHORI_PYTHON": sys.executable})

            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts" / "install_skill.sh"),
                    "--target",
                    "codex",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate Graphori installation", result.stderr)
            self.assertFalse((home / ".agents" / "skills" / "graphori").exists())


if __name__ == "__main__":
    unittest.main()
