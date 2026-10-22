"""A session's messages as the thread's turns: the user's, then one reply per turn.

opencode stores each step of a turn as its own assistant message; the thread
shows them as one reply, with its text and the steps taken to write it. A turn
opens with a `user` message and closes with an `idle` one, which says how it
ended. SurfSense's notes are `synthetic` messages beside the user's words, and
a compaction is a message of its own, never the reply.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from modules.agent.agent_threads.reply_ending import reply_ending
from modules.agent.agent_threads.scope_note import noted_scope
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


@dataclass
class Turn:
    """One user message, the notes sent with it, its steps and the message that closed it."""

    user: dict[str, Any]
    notes: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    idle: dict[str, Any] | None = None


def session_turns(messages: list[dict[str, Any]]) -> list[Turn]:
    """The session's turns, oldest first.

    A note goes with the user message it was sent beside: SurfSense sends it
    first, and a turn read back from opencode 1.x has it right after. 1.x also
    sent the user's message again after compacting an overflow; that copy
    carries the turn on.
    """
    turns: list[Turn] = []
    waiting: list[dict[str, Any]] = []
    compacted = False
    for message in messages:
        kind = message.get("type")
        current = turns[-1] if turns else None
        repeated = (
            compacted
            and current is not None
            and message.get("text") == current.user.get("text")
        )
        if kind != "synthetic":  # 1.x's "Continue…" came between
            compacted = kind == "compaction"
        if kind == "user" and repeated:
            continue
        if kind == "user":
            turns.append(Turn(message, notes=waiting))
            waiting = []
        elif kind == "synthetic":
            if current is not None and not current.steps and current.idle is None:
                current.notes.append(message)
            else:
                waiting.append(message)
        elif current is None:
            continue
        elif kind == "assistant":
            current.steps.append(message)
        elif kind == "idle":
            current.idle = message
    return turns


def thread_turns(
    messages: list[dict[str, Any]],
    citations: list[Citation],
    noted: dict[str, dict[str, Any]] | None = None,
    answering: bool = False,
) -> list[dict[str, Any]]:
    """Each user message followed by the reply its steps make up, oldest first.

    `noted` holds the endings SurfSense kept, by reply id; `answering` says the
    latest reply is still being written.
    """
    turns = session_turns(messages)
    shown: list[dict[str, Any]] = []
    for index, turn in enumerate(turns):
        user = turn.user
        created = iso_from_ms(user.get("time", {}).get("created"))
        shown.append(
            {
                "id": user["id"],
                "role": "user",
                "content": _user_content(turn),
                "created_at": created,
                "completed_at": created,
            }
        )
        live = answering and index == len(turns) - 1
        reply = _reply(turn, citations, noted, live)
        if reply is not None:
            shown.append(reply)
    return shown


def turn_reply(
    messages: list[dict[str, Any]],
    user_message_id: str,
    citations: list[Citation],
    noted: dict[str, dict[str, Any]] | None = None,
    live: bool = False,
) -> dict[str, Any] | None:
    """The reply to one user message, or None while the agent has written nothing.

    Its labels become citations as a chat answer's do; one the session's searches
    never returned is dropped.
    """
    for turn in session_turns(messages):
        if turn.user["id"] == user_message_id:
            return _reply(turn, citations, noted, live)
    return None


def _reply(
    turn: Turn,
    citations: list[Citation],
    noted: dict[str, dict[str, Any]] | None,
    live: bool,
) -> dict[str, Any] | None:
    """The reply that a turn's steps, given oldest first, make up."""
    steps = turn.steps
    if not steps:
        return None
    texts = [text for step in steps if (text := _text(step.get("content") or []))]
    tools = [
        step_of(item)
        for step in steps
        for item in step.get("content") or []
        if item.get("type") == "tool"
    ]
    text, cited = resolve_citations(PARAGRAPH.join(texts), citations)
    content: dict[str, Any] = {
        "text": text,
        "steps": tools,
        "citations": [asdict(citation) for citation in cited],
    }
    ending = reply_ending(
        steps, turn.idle, (noted or {}).get(reply_id(turn.user["id"])), live
    )
    if ending is not None:
        content["ending"] = ending
    return {
        "id": reply_id(turn.user["id"]),
        "role": "assistant",
        "content": content,
        "created_at": iso_from_ms(steps[0].get("time", {}).get("created")),
        "completed_at": iso_from_ms(steps[-1].get("time", {}).get("completed")),
    }


def _user_content(turn: Turn) -> dict[str, Any]:
    """The user's own words, and the sources the turn was given, without the note naming them.

    `scope` holds the ticked ids, or past the note's cap their count; the
    thread's reader names them.
    """
    content: dict[str, Any] = {"text": (turn.user.get("text") or "").strip()}
    scope = noted_scope(turn.notes)
    if scope is not None:
        content["scope"] = scope
    return content


def _text(items: list[dict[str, Any]]) -> str:
    """A step's answer text, without its reasoning or its tool calls; each item a paragraph."""
    return PARAGRAPH.join(
        text
        for item in items
        if item.get("type") == "text" and (text := (item.get("text") or "").strip())
    )
