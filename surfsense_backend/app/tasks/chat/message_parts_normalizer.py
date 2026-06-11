"""Normalize final LangChain assistant messages into assistant-ui parts.

Live streaming remains the primary source for rich, incremental UI state.
This module is only used after the graph has finished so refresh persistence
does not depend on provider-specific streaming chunk shapes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.messages import AIMessage


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        value = block.get("text") or block.get("content") or ""
        if isinstance(value, str) and value:
            text_parts.append(value)
    return "".join(text_parts)


def normalize_ai_message_to_parts(message: AIMessage | Any | None) -> list[dict[str, Any]]:
    """Return user-visible assistant-ui parts for a final AI message.

    We intentionally do not backfill provider ``thinking`` /
    ``reasoning_content`` blocks here. If reasoning streamed live, the
    ``AssistantContentBuilder`` already captured it. If it only exists in the
    final model payload, persisting it retroactively could expose content the
    UI never showed during the turn.
    """
    if message is None:
        return []

    text = _text_from_content(getattr(message, "content", None)).strip()
    if not text:
        return []
    return [{"type": "text", "text": text}]


def last_ai_message(messages: Iterable[Any] | None) -> AIMessage | Any | None:
    if messages is None:
        return None
    for message in reversed(list(messages)):
        if isinstance(message, AIMessage):
            return message
        if getattr(message, "type", None) == "ai":
            return message
    return None


def final_assistant_parts_from_messages(messages: Iterable[Any] | None) -> list[dict[str, Any]]:
    return normalize_ai_message_to_parts(last_ai_message(messages))


def has_non_empty_text_part(parts: Iterable[dict[str, Any]]) -> bool:
    return any(
        part.get("type") == "text"
        and isinstance(part.get("text"), str)
        and bool(part.get("text", "").strip())
        for part in parts
    )


def merge_streamed_and_final_parts(
    streamed_parts: list[dict[str, Any]],
    final_parts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use final-state text only when streaming captured no answer text."""
    if has_non_empty_text_part(streamed_parts):
        return streamed_parts
    if not has_non_empty_text_part(final_parts):
        return streamed_parts
    return [*streamed_parts, *final_parts]

