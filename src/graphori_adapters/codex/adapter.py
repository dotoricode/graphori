"""Execution adapter for the official non-interactive Codex CLI boundary."""

from __future__ import annotations

from pathlib import Path

from graphori_core.run_plan import NodeSpec

from graphori_adapters.agent_contract import AgentTaskEnvelope
from graphori_adapters.structured_cli import StructuredCliAdapter

from .protocol import CodexProtocolParser, render_codex_prompt


class CodexExecutionAdapter(StructuredCliAdapter):
    provider = "codex"
    adapter_id = "codex-cli"
    parser = CodexProtocolParser()
    required_help_tokens = ("--json", "--output-schema", "--ephemeral")
    required_resume_help_tokens = ("--json", "--output-schema", "--strict-config")

    def _help_argv(self) -> tuple[str, ...]:
        return (*self.executable, "exec", "--help")

    def _auth_argv(self) -> tuple[str, ...]:
        return (*self.executable, "login", "status")

    def _resume_help_argv(self) -> tuple[str, ...]:
        return (*self.executable, "exec", "resume", "--help")

    def _auth_ready(
            self, stdout: bytes, stderr: bytes, exit_code: int | None) -> bool:
        del stdout, stderr
        return exit_code == 0

    def _command(
            self, envelope: AgentTaskEnvelope, schema_path: Path,
            node: NodeSpec, *, persist_session: bool = False) -> tuple[str, ...]:
        sandbox = "workspace-write" if node.write_scope else "read-only"
        command = [
            *self.executable,
            "exec",
            "--json",
            "--output-schema", str(schema_path),
            "--color", "never",
            "--sandbox", sandbox,
        ]
        if not persist_session:
            command.append("--ephemeral")
        if node.model:
            command.extend(("--model", node.model))
        if node.effort:
            command.extend(("-c", f'model_reasoning_effort="{node.effort}"'))
        command.append(render_codex_prompt(envelope))
        return tuple(command)

    def _resume_command(
            self, prompt: str, session_id: str, schema_path: Path,
            node: NodeSpec) -> tuple[str, ...]:
        command = [
            *self.executable, "exec", "resume", "--json",
            "--output-schema", str(schema_path),
            "--strict-config",
        ]
        sandbox = "workspace-write" if node.write_scope else "read-only"
        command.extend(("-c", f'sandbox_mode="{sandbox}"'))
        if node.model:
            command.extend(("--model", node.model))
        if node.effort:
            command.extend(("-c", f'model_reasoning_effort="{node.effort}"'))
        command.extend((session_id, prompt))
        return tuple(command)
