"""Extract the agent's final assistant text from the terminal invoke result."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage


def extract_final_assistant_message(result: Any) -> str | None:
    """Return the last ``AIMessage`` text content, or ``None`` if there isn't one.

    Multi-part messages (content lists) are flattened by concatenating ``text``
    parts in order. Non-string content (tool calls, images) is skipped.
    """
    if not isinstance(result, dict):
        return None
    messages = result.get("messages")
    if not isinstance(messages, list):
        return None

    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        return _content_to_text(msg.content)
    return None


def _content_to_text(content: Any) -> str | None:
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        joined = "".join(parts).strip()
        return joined or None
    return None
