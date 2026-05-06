"""Interrupt-request events with a single canonical payload shape."""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter
from .data import format_data


def normalize_interrupt_payload(interrupt_value: dict[str, Any]) -> dict[str, Any]:
    if "action_requests" in interrupt_value and "review_configs" in interrupt_value:
        return interrupt_value

    interrupt_type = interrupt_value.get("type", "unknown")
    message = interrupt_value.get("message")
    action = interrupt_value.get("action", {}) or {}
    context = interrupt_value.get("context", {}) or {}

    normalized: dict[str, Any] = {
        "action_requests": [
            {
                "name": action.get("tool", "unknown_tool"),
                "args": action.get("params", {}),
            }
        ],
        "review_configs": [
            {
                "action_name": action.get("tool", "unknown_tool"),
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
        "interrupt_type": interrupt_type,
        "context": context,
    }
    if message:
        normalized["message"] = message
    return normalized


def format_interrupt_request(
    interrupt_value: dict[str, Any],
    *,
    interrupt_id: str | None = None,
    pending_interrupt_count: int | None = None,
    chat_turn_id: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload = normalize_interrupt_payload(interrupt_value)
    if interrupt_id is not None:
        payload["interrupt_id"] = interrupt_id
    if pending_interrupt_count is not None:
        payload["pending_interrupt_count"] = pending_interrupt_count
    if chat_turn_id is not None:
        payload["chat_turn_id"] = chat_turn_id
    return format_data("interrupt-request", payload, emitter=emitter)
