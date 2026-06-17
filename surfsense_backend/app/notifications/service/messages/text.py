"""Shared text helpers for notification copy."""

from __future__ import annotations

from app.notifications.constants import TITLE_MAX_LENGTH


def truncate(text: str, limit: int) -> str:
    """Return ``text`` capped at ``limit`` chars, appending an ellipsis if cut."""
    return text[:limit] + "..." if len(text) > limit else text


def format_title(prefix: str, text: str, *, max_length: int = TITLE_MAX_LENGTH) -> str:
    """Build a notification title that fits ``max_length`` including ``prefix``."""
    budget = max_length - len(prefix)
    if budget <= 0:
        return prefix[:max_length]
    if len(text) <= budget:
        return f"{prefix}{text}"
    if budget <= 3:
        return f"{prefix}{text[:budget]}"
    return f"{prefix}{text[: budget - 3]}..."
