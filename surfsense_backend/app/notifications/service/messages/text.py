"""Shared text helpers for notification copy."""

from __future__ import annotations


def truncate(text: str, limit: int) -> str:
    """Return ``text`` capped at ``limit`` chars, appending an ellipsis if cut."""
    return text[:limit] + "..." if len(text) > limit else text
