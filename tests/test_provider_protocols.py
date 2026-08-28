import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from graphori_adapters.agent_contract import (  # noqa: E402
    AgentTaskEnvelope, WorkerReport, worker_report_schema,
)
from graphori_adapters.claude.protocol import (  # noqa: E402
    ClaudeProtocolParser, render_claude_prompt,
)
from graphori_adapters.codex.protocol import (  # noqa: E402
    CodexProtocolParser, render_codex_prompt,
)
from graphori_adapters.provider_protocol import ProviderProtocolError  # noqa: E402
from graphori_core import ActivationScope, SkillBinding  # noqa: E402


REPORT = {
    "schema_version": 1,
    "status": "succeeded",
    "summary": "Implemented the bounded task.",
    "files_modified": ["src/a.py"],
    "evidence": [{"kind": "test", "reference": "python -m unittest"}],
    "limitations": ["No live integration test."],
}


class AgentContractTests(unittest.TestCase):
    def test_prompt_renderers_preserve_the_same_bounded_task_meaning(self):
        envelope = AgentTaskEnvelope(
            task_id="node-a", attempt_id="attempt:node-a:1",
            team="implementation", role="worker", objective="Change parser",
            constraints=("Do not delegate to another agent.",),
            working_directory=".", read_scope=("src/parser",),
            write_scope=("src/parser",),
            verification_expectation="Report evidence; do not claim verification PASS.",
        )
        codex = render_codex_prompt(envelope)
        claude = render_claude_prompt(envelope)
        for value in (
                "node-a", "attempt:node-a:1", "implementation", "Change parser",
                "src/parser", "Do not claim verification PASS",
                "status=succeeded reports task execution",
                "Do not create or delegate to nested agents"):
            self.assertIn(value, codex)
            self.assertIn(value, claude)
        self.assertLess(len(codex), 4000)
        self.assertLess(len(claude), 4000)

    def test_prompt_renderers_lazily_reference_the_same_pinned_skill(self):
        binding = SkillBinding(
            skill_id="ponytail", name="ponytail", digest="sha256:abc",
            snapshot_path=".graphori/skills/abc/SKILL.md", source_commit="abc123",
            arguments=(("mode", "full"),), reason="explicit_request",
            activation_scope=ActivationScope.ATTEMPT,
        )
        envelope = AgentTaskEnvelope(
            task_id="node-a", attempt_id="attempt:node-a:1",
            team="implementation", role="worker", objective="Change parser",
            skill_bindings=(binding,),
        )
        codex = render_codex_prompt(envelope)
        claude = render_claude_prompt(envelope)
        for prompt in (codex, claude):
            self.assertIn(".graphori/skills/abc/SKILL.md", prompt)
            self.assertIn("sha256:abc", prompt)
            self.assertIn("mode=full", prompt)
            self.assertIn("Do not execute package scripts or hooks", prompt)
        self.assertEqual(codex, claude)

    def test_worker_report_is_minimal_and_self_report_not_verdict(self):
        report = WorkerReport.from_mapping(REPORT)
        self.assertEqual(report.status, "succeeded")
        self.assertEqual(report.files_modified, ("src/a.py",))
        schema = worker_report_schema()
        self.assertNotIn("verification_passed", schema["properties"])
        self.assertNotIn("reasoning", schema["properties"])
        with self.assertRaises(ValueError):
            WorkerReport.from_mapping({**REPORT, "verification_passed": True})


class ProviderProtocolParserTests(unittest.TestCase):
    def test_codex_jsonl_extracts_final_report_and_preserves_unknown_event(self):
        lines = [
            {"type": "thread.started", "thread_id": "thr-1"},
            {"type": "future.event", "payload": {"safe": True}},
            {"type": "item.completed", "item": {
                "id": "item-1", "type": "agent_message", "text": json.dumps(REPORT),
            }},
            {"type": "turn.completed", "usage": {
                "input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 7,
            }},
        ]
        parsed = CodexProtocolParser().parse(
            b"\n".join(json.dumps(item).encode() for item in lines) + b"\n",
        )
        self.assertEqual(parsed.session_id, "thr-1")
        self.assertEqual(parsed.report, WorkerReport.from_mapping(REPORT))
        self.assertEqual(parsed.usage["input_tokens"], 12)
        self.assertEqual([event.known for event in parsed.events], [True, False, True, True])

    def test_claude_stream_extracts_structured_output_model_and_usage(self):
        lines = [
            {"type": "system", "subtype": "init", "session_id": "ses-1",
             "model": "claude-test", "capabilities": ["interrupt_receipt_v1"]},
            {"type": "future_message", "value": 1},
            {"type": "result", "subtype": "success", "is_error": False,
             "session_id": "ses-1", "structured_output": REPORT,
             "usage": {"input_tokens": 10, "output_tokens": 5},
             "total_cost_usd": 0.125},
        ]
        parsed = ClaudeProtocolParser().parse(
            b"\n".join(json.dumps(item).encode() for item in lines) + b"\n",
        )
        self.assertEqual(parsed.session_id, "ses-1")
        self.assertEqual(parsed.observed_model, "claude-test")
        self.assertEqual(parsed.report, WorkerReport.from_mapping(REPORT))
        self.assertEqual(parsed.usage["output_tokens"], 5)
        self.assertEqual(parsed.provider_reported_cost_usd, 0.125)
        self.assertEqual(parsed.capabilities, ("interrupt_receipt_v1",))

    def test_malformed_or_invalid_critical_result_fails_closed(self):
        for parser in (CodexProtocolParser(), ClaudeProtocolParser()):
            with self.subTest(parser=type(parser).__name__):
                with self.assertRaises(ProviderProtocolError):
                    parser.parse(b'{"type":"start"}\nnot-json\n')

        invalid_codex = {"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps({**REPORT, "status": "invented"}),
        }}
        with self.assertRaises(ProviderProtocolError):
            CodexProtocolParser().parse(json.dumps(invalid_codex).encode() + b"\n")

        invalid_claude = {
            "type": "result", "subtype": "success",
            "structured_output": {**REPORT, "status": "invented"},
        }
        with self.assertRaises(ProviderProtocolError):
            ClaudeProtocolParser().parse(json.dumps(invalid_claude).encode() + b"\n")

    def test_missing_final_report_is_observable_not_implicit_success(self):
        codex = CodexProtocolParser().parse(b'{"type":"turn.completed"}\n')
        claude = ClaudeProtocolParser().parse(
            b'{"type":"result","subtype":"success","result":"plain text"}\n',
        )
        self.assertIsNone(codex.report)
        self.assertIsNone(claude.report)


if __name__ == "__main__":
    unittest.main()
