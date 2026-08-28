"""Execution adapter for the official non-interactive Claude Code CLI boundary."""

from __future__ import annotations

import json
from pathlib import Path

from graphori_core.run_plan import NodeSpec

from graphori_adapters.agent_contract import (
    AgentTaskEnvelope,
    render_task_prompt,
    worker_report_schema,
)
from graphori_adapters.structured_cli import StructuredCliAdapter

from .protocol import ClaudeProtocolParser


class ClaudeCodeExecutionAdapter(StructuredCliAdapter):
    provider = "claude"
    adapter_id = "claude-code-cli"
    parser = ClaudeProtocolParser()
    required_help_tokens = (
        "-p", "--output-format", "--json-schema", "--no-session-persistence",
        "--permission-mode", "--allowedTools", "--disallowedTools",
        "--disable-slash-commands",
    )

    def _command(
            self, envelope: AgentTaskEnvelope, schema_path: Path,
            node: NodeSpec) -> tuple[str, ...]:
        del schema_path
        schema = worker_report_schema()
        # Claude Code validates the supplied schema with its bundled validator,
        # which rejects the otherwise standard draft URI as an unknown meta-schema.
        schema.pop("$schema", None)
        permission_mode = "acceptEdits" if node.write_scope else "plan"
        command = [
            *self.executable,
            "-p",
            render_task_prompt(envelope),
            "--output-format", "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--json-schema", json.dumps(schema, separators=(",", ":")),
            "--permission-mode", permission_mode,
            "--disallowedTools", "Agent",
            "--disable-slash-commands",
        ]
        if node.write_scope:
            command.extend((
                "--allowedTools",
                "Bash(python -m unittest *),Bash(python3 -m unittest *)",
            ))
        if node.model:
            command.extend(("--model", node.model))
        if node.effort:
            command.extend(("--effort", node.effort))
        return tuple(command)
