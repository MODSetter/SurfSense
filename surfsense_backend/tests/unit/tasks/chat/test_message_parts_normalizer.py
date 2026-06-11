"""Unit tests for final assistant message part normalization."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.tasks.chat.message_parts_normalizer import (
    final_assistant_parts_from_messages,
    merge_streamed_and_final_parts,
    normalize_ai_message_to_parts,
)

pytestmark = pytest.mark.unit


def test_string_ai_message_content_becomes_text_part() -> None:
    assert normalize_ai_message_to_parts(AIMessage(content="hello")) == [
        {"type": "text", "text": "hello"}
    ]


def test_deepseek_thinking_plus_text_blocks_backfill_only_text() -> None:
    message = AIMessage(
        content=[
            {"type": "thinking", "thinking": "hidden reasoning"},
            {"type": "text", "text": "Yo bro! What's up?"},
        ],
        additional_kwargs={"reasoning_content": "hidden reasoning"},
    )

    assert normalize_ai_message_to_parts(message) == [
        {"type": "text", "text": "Yo bro! What's up?"}
    ]


def test_final_parts_use_last_ai_message_and_skip_trailing_tool_messages() -> None:
    messages = [
        HumanMessage(content="ask"),
        AIMessage(content="draft"),
        ToolMessage(content="tool output", tool_call_id="tc-1"),
        AIMessage(content=[{"type": "text", "text": "final answer"}]),
        ToolMessage(content="trailing tool noise", tool_call_id="tc-2"),
    ]

    assert final_assistant_parts_from_messages(messages) == [
        {"type": "text", "text": "final answer"}
    ]


def test_merge_adds_final_text_when_stream_only_has_thinking_steps() -> None:
    streamed = [
        {
            "type": "data-thinking-steps",
            "data": [{"id": "thinking-1", "status": "completed"}],
        }
    ]
    final = [{"type": "text", "text": "visible answer"}]

    assert merge_streamed_and_final_parts(streamed, final) == [*streamed, *final]


def test_merge_does_not_duplicate_when_stream_already_has_text() -> None:
    streamed = [{"type": "text", "text": "streamed answer"}]
    final = [{"type": "text", "text": "final answer"}]

    assert merge_streamed_and_final_parts(streamed, final) == streamed

