"""Extract displayable text from a LangGraph agent ``invoke`` / ``ainvoke`` result."""

from __future__ import annotations

from typing import Any


def extract_last_assistant_text(result: dict[str, Any]) -> str:
    """Return the last message's string content, or ``\"\"`` if missing."""
    messages = result.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", None)
    if isinstance(content, str):
        return content
    return str(last)
