"""Pin the exact SSE wire bytes the FE parser depends on."""

from __future__ import annotations

import json

import pytest

from app.services.streaming.envelope import (
    format_done,
    format_sse,
    get_response_headers,
)

pytestmark = pytest.mark.unit


class TestFormatSse:
    def test_dict_payload_is_json_serialised(self) -> None:
        frame = format_sse({"type": "start", "messageId": "msg_1"})
        assert frame.startswith("data: ")
        assert frame.endswith("\n\n")
        body = frame[len("data: ") : -2]
        assert json.loads(body) == {"type": "start", "messageId": "msg_1"}

    def test_string_payload_is_emitted_verbatim(self) -> None:
        frame = format_sse('{"already":"json"}')
        assert frame == 'data: {"already":"json"}\n\n'

    def test_nested_payload_round_trips(self) -> None:
        payload = {
            "type": "data-action-log",
            "data": {"id": 7, "tool_name": "ls", "reversible": False},
        }
        frame = format_sse(payload)
        body = frame.removeprefix("data: ").removesuffix("\n\n")
        assert json.loads(body) == payload


class TestFormatDone:
    def test_done_marker_is_literal(self) -> None:
        assert format_done() == "data: [DONE]\n\n"


class TestResponseHeaders:
    def test_headers_pin_ai_sdk_v1_protocol(self) -> None:
        headers = get_response_headers()
        assert headers["Content-Type"] == "text/event-stream"
        assert headers["Cache-Control"] == "no-cache"
        assert headers["Connection"] == "keep-alive"
        assert headers["x-vercel-ai-ui-message-stream"] == "v1"
