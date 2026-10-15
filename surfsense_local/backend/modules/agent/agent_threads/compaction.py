"""opencode's own messages when it compacts a session mid-turn, told apart from the conversation.

When the window fills, opencode adds a user message holding a compaction part,
an assistant summary written for itself, and then a user message that carries
the turn on: a synthetic "Continue…" or, after an overflow, the user's message
again (opencode 1.18.32, session/compaction.ts). None of them is the user's,
and the summary is not the reply.
"""

from typing import Any


def is_summary(info: dict[str, Any]) -> bool:
    """Whether a message is a compaction's summary, which only opencode reads."""
    return info.get("role") == "assistant" and (
        info.get("summary") is True or info.get("mode") == "compaction"
    )


def turn_openers(messages: list[dict[str, Any]]) -> dict[str, str]:
    """Each user message's id, mapped to the id of the user's message that opened its turn."""
    openers: dict[str, str] = {}
    opener: str | None = None
    carries_on = False
    for message in messages:
        info = message["info"]
        if info["role"] == "user":
            if opener is None or not (carries_on or _starts_compaction(message)):
                opener = info["id"]
            openers[info["id"]] = opener
        # Only a summary that finished cleanly is followed by a message carrying the turn on.
        carries_on = (
            is_summary(info) and bool(info.get("finish")) and not info.get("error")
        )
    return openers


def _starts_compaction(message: dict[str, Any]) -> bool:
    return any(part.get("type") == "compaction" for part in message["parts"])
