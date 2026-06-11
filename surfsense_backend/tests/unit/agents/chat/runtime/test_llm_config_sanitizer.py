"""Regression tests for model-boundary message sanitization."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.agents.chat.runtime.llm_config import _sanitize_messages

pytestmark = pytest.mark.unit


def test_sanitize_messages_strips_provider_specific_thinking_blocks() -> None:
    original = AIMessage(
        content=[
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": "visible answer"},
        ]
    )

    sanitized = _sanitize_messages([original])

    assert sanitized[0].content == "visible answer"
    assert original.content == [
        {"type": "thinking", "thinking": "private reasoning"},
        {"type": "text", "text": "visible answer"},
    ]


def test_sanitize_messages_sets_tool_only_ai_content_to_none() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "call_1"}],
    )

    sanitized = _sanitize_messages([message])

    assert sanitized[0].content is None
    assert message.content == ""

