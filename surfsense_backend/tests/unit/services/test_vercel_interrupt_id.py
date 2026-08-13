"""``VercelStreamingService.format_interrupt_request`` carries ``interrupt_id`` on the wire.

Parent-side interrupts (doom-loop, permission asks) have no ``tool_call_id``; the
langgraph ``Interrupt.id`` is their only stable handle, so the frontend can only
render and resume them when it arrives on the frame.
"""

from __future__ import annotations

import json

import pytest

from app.services.new_streaming_service import VercelStreamingService

pytestmark = pytest.mark.unit


def _payload(frame: str) -> dict:
    body = frame.removeprefix("data: ").removesuffix("\n\n")
    return json.loads(body)["data"]


def test_interrupt_id_present_when_supplied() -> None:
    frame = VercelStreamingService().format_interrupt_request(
        {"type": "permission_ask", "action": {"tool": "search", "params": {}},
         "context": {"permission": "doom_loop"}},
        interrupt_id="int_7",
    )
    assert _payload(frame)["interrupt_id"] == "int_7"


def test_interrupt_id_omitted_when_absent() -> None:
    frame = VercelStreamingService().format_interrupt_request(
        {"action_requests": [], "review_configs": []},
    )
    assert "interrupt_id" not in _payload(frame)


def test_does_not_mutate_source_value() -> None:
    """Subagent payloads pass through by reference — stamping must not touch state."""
    value = {"action_requests": [{"name": "x", "args": {}}], "review_configs": [{}]}
    VercelStreamingService().format_interrupt_request(value, interrupt_id="int_9")
    assert "interrupt_id" not in value
