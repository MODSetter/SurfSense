"""Data shapes for a resolved referenced chat and its turns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferencedChatTurn:
    """One visible turn of a referenced conversation."""

    role: str  # "user" | "assistant"
    text: str


@dataclass(frozen=True)
class ReferencedChat:
    """A referenced conversation, in chronological turn order."""

    thread_id: int
    title: str
    turns: list[ReferencedChatTurn]


__all__ = ["ReferencedChat", "ReferencedChatTurn"]
