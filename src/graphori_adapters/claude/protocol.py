"""Parser and prompt renderer for Claude Code ``stream-json`` output."""

from __future__ import annotations

from typing import Mapping

from graphori_adapters.agent_contract import AgentTaskEnvelope, render_task_prompt
from graphori_adapters.provider_protocol import (
    NormalizedProviderEvent,
    ProviderParseResult,
    ProviderProtocolError,
    decode_json_lines,
    parse_report,
)


_KNOWN_EVENTS = frozenset({"system", "assistant", "user", "stream_event", "result"})


def render_claude_prompt(envelope: AgentTaskEnvelope) -> str:
    return render_task_prompt(envelope)


class ClaudeProtocolParser:
    """Normalize Claude Code stream-json without treating it as a verdict."""

    def parse(self, data: bytes) -> ProviderParseResult:
        events: list[NormalizedProviderEvent] = []
        report = None
        session_id = ""
        observed_model = ""
        usage: Mapping[str, int] = {}
        provider_reported_cost_usd: float | None = None
        capabilities: tuple[str, ...] = ()
        for value in decode_json_lines(data):
            event_type = value.get("type")
            if not isinstance(event_type, str) or not event_type:
                raise ProviderProtocolError("Claude event type is missing")
            known = event_type in _KNOWN_EVENTS
            events.append(NormalizedProviderEvent("claude", event_type, known, value))
            incoming_session = value.get("session_id")
            if isinstance(incoming_session, str):
                session_id = incoming_session
            if event_type == "system" and value.get("subtype") == "init":
                model = value.get("model")
                if isinstance(model, str):
                    observed_model = model
                raw_capabilities = value.get("capabilities")
                if isinstance(raw_capabilities, list) and all(
                        isinstance(item, str) for item in raw_capabilities):
                    capabilities = tuple(raw_capabilities)
            elif event_type == "result":
                raw_cost = value.get("total_cost_usd")
                if isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool):
                    provider_reported_cost_usd = float(raw_cost)
                raw_usage = value.get("usage")
                if isinstance(raw_usage, Mapping):
                    usage = {
                        str(key): item for key, item in raw_usage.items()
                        if isinstance(item, int) and not isinstance(item, bool)
                    }
                if "structured_output" in value:
                    report = parse_report(value["structured_output"], provider="Claude")
        return ProviderParseResult(
            provider="claude", events=tuple(events), report=report,
            session_id=session_id, observed_model=observed_model,
            usage=usage, capabilities=capabilities,
            provider_reported_cost_usd=provider_reported_cost_usd,
        )
