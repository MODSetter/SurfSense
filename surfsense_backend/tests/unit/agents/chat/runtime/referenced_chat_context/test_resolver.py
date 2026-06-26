"""Tests for referenced-chat message text extraction."""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.referenced_chat_context.resolver import _visible_text
from app.db import NewChatMessage, NewChatMessageRole

pytestmark = pytest.mark.unit


def _message(role: NewChatMessageRole, content: object) -> NewChatMessage:
    return NewChatMessage(role=role, content=content)


def test_assistant_text_drops_reasoning_and_keeps_visible_text() -> None:
    message = _message(
        NewChatMessageRole.ASSISTANT,
        [
            {"type": "thinking", "thinking": "private"},
            {"type": "text", "text": "visible answer"},
        ],
    )

    assert _visible_text(message) == "visible answer"


def test_user_text_drops_images_and_keeps_text() -> None:
    message = _message(
        NewChatMessageRole.USER,
        [
            {"type": "text", "text": "look at this"},
            {"type": "image", "image": "data:image/png;base64,AAA"},
        ],
    )

    assert _visible_text(message) == "look at this"


def test_plain_string_content_is_returned_as_is() -> None:
    message = _message(NewChatMessageRole.USER, "just text")

    assert _visible_text(message) == "just text"
