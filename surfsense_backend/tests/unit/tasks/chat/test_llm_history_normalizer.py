"""Unit tests for provider-safe LLM history normalization."""

from __future__ import annotations

import pytest

from app.tasks.chat.llm_history_normalizer import (
    assistant_content_to_llm_text,
    user_content_to_llm_content,
)

pytestmark = pytest.mark.unit


def test_assistant_ui_parts_drop_thinking_steps_for_llm_history() -> None:
    content = [
        {"type": "data-thinking-steps", "data": [{"id": "thinking-1"}]},
        {"type": "text", "text": "visible answer"},
    ]

    assert assistant_content_to_llm_text(content) == "visible answer"


def test_provider_thinking_blocks_are_not_replayed_to_llm() -> None:
    content = [
        {"type": "thinking", "thinking": "private reasoning"},
        {"type": "text", "text": "final answer"},
    ]

    assert assistant_content_to_llm_text(content) == "final answer"


def test_unknown_assistant_blocks_are_dropped() -> None:
    content = [
        {"type": "redacted_thinking", "data": "hidden"},
        {"type": "tool_use", "name": "search"},
        {"type": "text", "text": "kept"},
    ]

    assert assistant_content_to_llm_text(content) == "kept"


def test_user_images_convert_to_openai_compatible_image_url_blocks() -> None:
    content = [
        {"type": "text", "text": "look"},
        {"type": "image", "image": "data:image/png;base64,abc"},
    ]

    assert user_content_to_llm_content(content, allow_images=True) == [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
    ]


def test_user_images_can_be_dropped_for_text_only_history() -> None:
    content = [
        {"type": "text", "text": "look"},
        {"type": "image", "image": "data:image/png;base64,abc"},
    ]

    assert user_content_to_llm_content(content, allow_images=False) == "look"
