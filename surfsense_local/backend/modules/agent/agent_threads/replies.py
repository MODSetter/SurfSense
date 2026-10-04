"""A session's messages as the thread's turns: the user's, then one reply per turn.

opencode starts a new assistant message for every step of a turn; the thread
shows them as one reply, with its text and the steps taken to write it. A
compaction's own messages fold into the turn it happened in.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from modules.agent.agent_threads.compaction import is_summary, turn_openers
from modules.agent.agent_threads.scope_note import is_scope_note, noted_scope
from modules.agent.agent_threads.steps import step_of
from modules.chat.prompt import Citation, resolve_citations

# Between two parts of a reply's text: each step's words start with no break of their own.
PARAGRAPH = "\n\n"


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


def thread_turns(
    messages: list[dict[str, Any]], citations: list[Citation]
) -> list[dict[str, Any]]:
    """Each user message followed by the reply its steps make up, oldest first."""
    turns: list[dict[str, Any]] = []
    openers = turn_openers(messages)
    for message in messages:
        info = message["info"]
        if info["role"] != "user" or openers[info["id"]] != info["id"]:
            continue
        created = iso_from_ms(info.get("time", {}).get("created"))
        turns.append(
            {
                "id": info["id"],
                "role": "user",
                "content": _user_content(message["parts"]),
                "created_at": created,
                "completed_at": created,
            }
        )
        reply = turn_reply(messages, info["id"], citations)
        if reply is not None:
            turns.append(reply)
    return turns


def turn_reply(
    messages: list[dict[str, Any]], user_message_id: str, citations: list[Citation]
) -> dict[str, Any] | None:
    """The reply to one user message, or None while the agent has written nothing.

    Its labels become citations as a chat answer's do; one the session's searches
    never returned is dropped.
    """
    in_turn = {
        message_id
        for message_id, opener in turn_openers(messages).items()
        if opener == user_message_id
    }
    steps = [
        m
        for m in messages
        if m["info"]["role"] == "assistant"
        and m["info"].get("parentID") in in_turn
        and not is_summary(m["info"])
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
    text, cited = resolve_citations(PARAGRAPH.join(texts), citations)
    return {
        "id": reply_id(user_message_id),
        "role": "assistant",
        "content": {
            "text": text,
            "steps": tools,
            "citations": [asdict(citation) for citation in cited],
        },
        "created_at": iso_from_ms(times[0].get("created")),
        "completed_at": iso_from_ms(times[-1].get("completed")),
    }


def _user_content(parts: list[dict[str, Any]]) -> dict[str, Any]:
    """The user's own words, and the sources the turn was given, without the note naming them.

    `scope` holds the ticked ids; the thread's reader names them.
    """
    content: dict[str, Any] = {
        "text": _text([part for part in parts if not is_scope_note(part)])
    }
    scope = noted_scope(parts)
    if scope is not None:
        content["scope"] = {"document_ids": scope}
    return content


def _text(parts: list[dict[str, Any]]) -> str:
    """A message's answer text, without its reasoning or its tool calls; each part a paragraph."""
    return PARAGRAPH.join(
        text
        for part in parts
        if part.get("type") == "text" and (text := (part.get("text") or "").strip())
    )
