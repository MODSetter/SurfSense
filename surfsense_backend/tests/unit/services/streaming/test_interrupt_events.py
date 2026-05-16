"""Pin interrupt-payload normalisation and the optional correlation fields on the wire."""

from __future__ import annotations

import json

import pytest

from app.services.streaming.events.interrupt import (
    format_interrupt_request,
    normalize_interrupt_payload,
)

pytestmark = pytest.mark.unit


def _decode(frame: str) -> dict:
    body = frame.removeprefix("data: ").removesuffix("\n\n")
    return json.loads(body)


def test_hitlrequest_shape_is_passed_through_unchanged() -> None:
    raw = {
        "action_requests": [{"name": "send_email", "args": {"to": "a@b"}}],
        "review_configs": [
            {"action_name": "send_email", "allowed_decisions": ["approve"]}
        ],
    }
    assert normalize_interrupt_payload(raw) == raw


def test_custom_interrupt_primitive_is_converted_to_canonical_shape() -> None:
    raw = {
        "type": "permission",
        "message": "Allow send?",
        "action": {"tool": "send_email", "params": {"to": "a@b"}},
        "context": {"reason": "destructive"},
    }
    out = normalize_interrupt_payload(raw)
    assert out["action_requests"] == [{"name": "send_email", "args": {"to": "a@b"}}]
    assert out["review_configs"] == [
        {
            "action_name": "send_email",
            "allowed_decisions": ["approve", "edit", "reject"],
        }
    ]
    assert out["interrupt_type"] == "permission"
    assert out["message"] == "Allow send?"
    assert out["context"] == {"reason": "destructive"}


def test_custom_interrupt_without_message_omits_message_key() -> None:
    """Optional fields stay optional on the wire; FE does not see ``"message": None``."""
    raw = {"action": {"tool": "send_email"}}
    out = normalize_interrupt_payload(raw)
    assert "message" not in out


def test_custom_interrupt_without_tool_falls_back_to_unknown_tool() -> None:
    """Defensive: a malformed ``action`` block must not crash the relay."""
    out = normalize_interrupt_payload({"type": "x", "action": {}})
    assert out["action_requests"][0]["name"] == "unknown_tool"
    assert out["review_configs"][0]["action_name"] == "unknown_tool"


def test_format_interrupt_request_carries_correlation_fields_on_the_wire() -> None:
    frame = format_interrupt_request(
        {"action_requests": [], "review_configs": []},
        interrupt_id="int_42",
        pending_interrupt_count=3,
        chat_turn_id="turn_99",
    )
    payload = _decode(frame)
    assert payload["type"] == "data-interrupt-request"
    inner = payload["data"]
    assert inner["interrupt_id"] == "int_42"
    assert inner["pending_interrupt_count"] == 3
    assert inner["chat_turn_id"] == "turn_99"


def test_format_interrupt_request_omits_correlation_fields_when_unset() -> None:
    """Backward compat: legacy single-interrupt callers don't have to supply ids."""
    frame = format_interrupt_request(
        {"action_requests": [], "review_configs": []},
    )
    inner = _decode(frame)["data"]
    assert "interrupt_id" not in inner
    assert "pending_interrupt_count" not in inner
    assert "chat_turn_id" not in inner
