"""Parser and prompt renderer for ``codex exec --json``."""

from __future__ import annotations

import json
from typing import Any, Mapping

from graphori_adapters.agent_contract import AgentTaskEnvelope, render_task_prompt
from graphori_adapters.provider_protocol import (
    NormalizedProviderEvent,
    ProviderParseResult,
    ProviderProtocolError,
    decode_json_lines,
    parse_report,
)


_KNOWN_EVENTS = frozenset({
    "thread.started", "turn.started", "turn.completed", "turn.failed", "item.started",
    "item.updated", "item.completed", "error",
})


def render_codex_prompt(envelope: AgentTaskEnvelope) -> str:
    return render_task_prompt(envelope)


class CodexProtocolParser:
    """Normalize Codex JSONL while retaining provider ownership of events."""

    def parse(self, data: bytes) -> ProviderParseResult:
        events: list[NormalizedProviderEvent] = []
        report = None
        session_id = ""
        observed_model = ""
        usage: Mapping[str, int] = {}
        for value in decode_json_lines(data):
            event_type = value.get("type")
            if not isinstance(event_type, str) or not event_type:
                raise ProviderProtocolError("Codex event type is missing")
            known = event_type in _KNOWN_EVENTS
            events.append(NormalizedProviderEvent("codex", event_type, known, value))
            if event_type == "thread.started":
                thread_id = value.get("thread_id")
                if isinstance(thread_id, str):
                    session_id = thread_id
            elif event_type == "turn.completed":
                raw_usage = value.get("usage")
                if isinstance(raw_usage, Mapping):
                    usage = {
                        str(key): item for key, item in raw_usage.items()
                        if isinstance(item, int) and not isinstance(item, bool)
                    }
                model = value.get("model")
                if isinstance(model, str):
                    observed_model = model
            elif event_type == "item.completed":
                item = value.get("item")
                if isinstance(item, Mapping) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if not isinstance(text, str):
                        raise ProviderProtocolError("Codex final agent_message text is invalid")
                    try:
                        candidate: Any = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    report = parse_report(candidate, provider="Codex")
        return ProviderParseResult(
            provider="codex", events=tuple(events), report=report, session_id=session_id,
            observed_model=observed_model, usage=usage,
        )
