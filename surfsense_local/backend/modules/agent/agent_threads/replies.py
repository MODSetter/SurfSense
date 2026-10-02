"""A session's messages as the thread's turns: the user's, then one reply per turn.

opencode starts a new assistant message for every step of a turn; the thread
shows them as one reply, with its text and the steps taken to write it.
"""

from datetime import UTC, datetime
from typing import Any

from modules.agent.agent_threads.steps import step_of


def reply_id(user_message_id: str) -> str:
    """The id a turn's reply goes by, stable from the first frame to the stored turn."""
    return f"{user_message_id}:reply"


def iso_from_ms(milliseconds: int | None) -> str | None:
    """An opencode timestamp, spelled as the REST timestamps are: UTC as Z."""
    if milliseconds is None:
        return None
    return (
        datetime.fromtimestamp(milliseconds / 1000, UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


def thread_turns(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each user message followed by the reply its steps make up, oldest first."""
    turns: list[dict[str, Any]] = []
    for message in messages:
        info = message["info"]
        if info["role"] != "user":
            continue
        created = iso_from_ms(info.get("time", {}).get("created"))
        turns.append(
            {
                "id": info["id"],
                "role": "user",
                "content": {"text": _text(message["parts"])},
                "created_at": created,
                "completed_at": created,
            }
        )
        reply = turn_reply(messages, info["id"])
        if reply is not None:
            turns.append(reply)
    return turns


def turn_reply(
    messages: list[dict[str, Any]], user_message_id: str
) -> dict[str, Any] | None:
    """The reply to one user message, or None while the agent has written nothing."""
    steps = [
        m
        for m in messages
        if m["info"]["role"] == "assistant"
        and m["info"].get("parentID") == user_message_id
    ]
    if not steps:
        return None
    texts = [text for step in steps if (text := _text(step["parts"]))]
    tools = [
        step_of(part)
        for step in steps
        for part in step["parts"]
        if part.get("type") == "tool"
    ]
    times = [step["info"].get("time", {}) for step in steps]
    return {
        "id": reply_id(user_message_id),
        "role": "assistant",
        "content": {"text": "\n\n".join(texts), "steps": tools},
        "created_at": iso_from_ms(times[0].get("created")),
        "completed_at": iso_from_ms(times[-1].get("completed")),
    }


def _text(parts: list[dict[str, Any]]) -> str:
    """A message's answer text, without its reasoning or its tool calls."""
    return "".join(
        part.get("text") or "" for part in parts if part.get("type") == "text"
    ).strip()
