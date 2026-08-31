#!/usr/bin/env python3
"""Validate the Graphori skill without third-party packages.

This intentionally checks the small, documented YAML subset used by
``agents/openai.yaml`` instead of importing a YAML parser.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


COMMON_UTF8_FILES = (
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
)


def fail(message: str) -> None:
    raise ValueError(message)


def read_utf8(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        fail(f"{path}: UTF-8 BOM is not allowed")
    if b"\r" in data:
        fail(f"{path}: CRLF or CR line endings are not allowed")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{path}: file is not valid UTF-8 ({exc})")


def validate_frontmatter(path: Path, text: str, expected_name: str) -> None:
    lines = text.splitlines()
    if len(lines) < 4 or lines[0] != "---":
        fail(f"{path}: frontmatter must start with ---")

    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"{path}: frontmatter closing --- is missing")

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            fail(f"{path}: invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in fields:
            fail(f"{path}: duplicate frontmatter key: {key}")
        fields[key] = value

    if fields.get("name") != expected_name:
        fail(f"{path}: frontmatter name must be {expected_name}")
    if not fields.get("description"):
        fail(f"{path}: frontmatter description must not be empty")


_QUOTED_VALUE = re.compile(r'^"(?:\\.|[^"\\])*"$')


def validate_openai_yaml(path: Path, text: str, expected_invocation: str) -> None:
    values: dict[str, str] = {}
    lines = text.splitlines()
    if lines != [line.rstrip() for line in lines]:
        fail(f"{path}: trailing whitespace is not allowed")
    if not lines or lines[0] != "interface:":
        fail(f"{path}: interface mapping is required")

    for line in lines[1:]:
        match = re.fullmatch(r"  ([a-z_]+): (.+)", line)
        if not match:
            fail(f"{path}: unsupported or malformed line: {line!r}")
        key, raw_value = match.groups()
        if key in values:
            fail(f"{path}: duplicate key: {key}")
        if not _QUOTED_VALUE.fullmatch(raw_value):
            fail(f"{path}: {key} must use double quotes")
        values[key] = raw_value[1:-1]

    required = {"display_name", "short_description", "default_prompt"}
    if set(values) != required:
        missing = sorted(required - set(values))
        extra = sorted(set(values) - required)
        fail(f"{path}: required keys mismatch (missing={missing}, extra={extra})")
    for key, value in values.items():
        if not value:
            fail(f"{path}: {key} must not be empty")
    if expected_invocation not in values["default_prompt"]:
        fail(f"{path}: default_prompt must contain {expected_invocation}")


def validate(root: Path) -> None:
    root = root.resolve()
    expected_name = root.name
    skill_path = root / "SKILL.md"
    yaml_path = root / "agents" / "openai.yaml"
    if not skill_path.is_file():
        fail(f"missing file: {skill_path}")
    if not yaml_path.is_file():
        fail(f"missing file: {yaml_path}")

    required_files = list(COMMON_UTF8_FILES)
    if expected_name == "graphori":
        required_files.extend((
            Path("references/canonical-routing.md"),
            Path("references/proof-driven-execution.md"),
        ))
    texts: dict[Path, str] = {}
    for relative in required_files:
        path = root / relative
        if not path.is_file():
            fail(f"missing file: {path}")
        texts[relative] = read_utf8(path)

    validate_frontmatter(Path("SKILL.md"), texts[Path("SKILL.md")], expected_name)
    validate_openai_yaml(
        Path("agents/openai.yaml"), texts[Path("agents/openai.yaml")],
        f"${expected_name}",
    )


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print(f"usage: {Path(argv[0]).name} [skill-directory]", file=sys.stderr)
        return 2
    root = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parents[1]
    try:
        validate(root)
    except (OSError, ValueError) as exc:
        print(f"Skill is invalid: {exc}", file=sys.stderr)
        return 1
    print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
