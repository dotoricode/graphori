"""Deterministic Orca Delivery to Graphori runtime-event translation."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from graphori_core.ports import RuntimeEvent

from .protocol import OrcaProtocolError


class OrcaJournalBridge:
    """Translate delivery data; the Engine durably appends before ACK."""

    @staticmethod
    def _identity(delivery_id: str, message_id: str) -> str:
        body = json.dumps(
            ["orca", delivery_id, message_id], separators=(",", ":"),
        ).encode("utf-8")
        return "orca:" + hashlib.sha256(body).hexdigest()

    def events(
            self, delivery: Mapping[str, Any], *, node_id: str,
            expected_task_id: str, expected_dispatch_id: str) -> tuple[RuntimeEvent, ...]:
        delivery_id = delivery.get("id")
        messages = delivery.get("messages")
        if not isinstance(delivery_id, str) or not delivery_id:
            raise OrcaProtocolError("Delivery id is required")
        if not isinstance(messages, list):
            raise OrcaProtocolError("Delivery messages must be an array")
        events: list[RuntimeEvent] = []
        for message in messages:
            if not isinstance(message, Mapping):
                raise OrcaProtocolError("Delivery message must be an object")
            if message.get("type") != "worker_done":
                continue
            message_id = message.get("id")
            task_id = message.get("taskId", message.get("task_id"))
            dispatch_id = message.get("dispatchId", message.get("dispatch_id"))
            if not isinstance(message_id, str) or not message_id:
                raise OrcaProtocolError("worker_done message id is required")
            if task_id != expected_task_id or dispatch_id != expected_dispatch_id:
                continue
            outcome = message.get("outcome")
            if outcome not in {"succeeded", "failed"}:
                raise OrcaProtocolError("worker_done outcome must be succeeded or failed")
            files = message.get("filesModified", message.get("files_modified", []))
            if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
                raise OrcaProtocolError("worker_done filesModified must be a string array")
            event_id = self._identity(delivery_id, message_id)
            events.append(RuntimeEvent(
                "worker_finished", node_id, "worker",
                {
                    "outcome": outcome,
                    "summary": str(message.get("body", "")),
                    "reported_files_modified": files,
                    "source": "orca_delivery",
                    "external_task_id": task_id,
                    "external_dispatch_id": dispatch_id,
                    "_orca_delivery_id": delivery_id,
                },
                event_id=event_id,
                producer_event_id=event_id,
            ))
        return tuple(events)
