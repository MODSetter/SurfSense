"""A turn opencode compacted partway: the user's message and the agent's answer, without opencode's own notes.

The message shapes are opencode 1.18.32's (session/compaction.ts): a user
message holding a compaction part, an assistant summary, then a user message
that carries the turn on.
"""

from collections.abc import Callable
from typing import Any

import pytest

from modules.agent.agent_threads.replies import thread_turns, turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.opencode_client import Event

pytestmark = pytest.mark.unit

SESSION = "ses_1"
SUMMARY = "## Objective\nDraft the proposal."


def _user(message_id: str, *parts: dict[str, Any]) -> dict[str, Any]:
    return {
        "info": {"id": message_id, "role": "user", "time": {"created": 1}},
        "parts": list(parts) or [{"type": "text", "text": f"Asked in {message_id}"}],
    }


def _assistant(
    message_id: str, parent: str, text: str = "", **info: Any
) -> dict[str, Any]:
    parts = [{"type": "text", "text": text}] if text else []
    return {
        "info": {
            "id": message_id,
            "role": "assistant",
            "parentID": parent,
            "time": {"created": 2, "completed": 3},
            "finish": "stop",
            **info,
        },
        "parts": parts,
    }


def _summary(message_id: str, parent: str, **info: Any) -> dict[str, Any]:
    return _assistant(
        message_id, parent, SUMMARY, summary=True, mode="compaction", **info
    )


COMPACTION = {"type": "compaction", "auto": True, "overflow": False}
CONTINUE = {
    "type": "text",
    "synthetic": True,
    "text": "Continue if you have next steps, or stop and ask for clarification "
    "if you are unsure how to proceed.",
    "metadata": {"compaction_continue": True},
}


def test_the_answer_after_a_compaction_is_the_turns_reply() -> None:
    """opencode answers the continuation it added, not the user's message."""
    messages = [
        _user("u1"),
        _assistant("a1", "u1", finish="tool-calls"),
        _user("c1", COMPACTION),
        _summary("s1", "c1"),
        _user("k1", CONTINUE),
        _assistant("a2", "k1", "The proposal is in Studio."),
    ]

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == "The proposal is in Studio."
    assert [(t["role"], t["content"]["text"]) for t in thread_turns(messages, [])] == [
        ("user", "Asked in u1"),
        ("assistant", "The proposal is in Studio."),
    ]


def test_a_turn_replayed_after_an_overflow_stays_one_turn() -> None:
    """A request too large for the provider is compacted and the user's message sent again."""
    messages = [
        _user("u1"),
        _user("c1", {**COMPACTION, "overflow": True}),
        _summary("s1", "c1"),
        _user("r1", {"type": "text", "text": "Asked in u1"}),
        _assistant("a1", "r1", "Done."),
    ]

    assert [(t["role"], t["content"]["text"]) for t in thread_turns(messages, [])] == [
        ("user", "Asked in u1"),
        ("assistant", "Done."),
    ]


def test_after_a_failed_compaction_the_next_message_is_the_users() -> None:
    """A summary that failed ends the turn; nothing carries it on."""
    messages = [
        _user("u1"),
        _user("c1", COMPACTION),
        _summary("s1", "c1", finish="error", error={"name": "ContextOverflowError"}),
        _user("u2"),
        _assistant("a2", "u2", "Here it is."),
    ]

    turns = [(t["role"], t["content"]["text"]) for t in thread_turns(messages, [])]

    assert turns == [
        ("user", "Asked in u1"),
        ("user", "Asked in u2"),
        ("assistant", "Here it is."),
    ]


def _stream(turn: TurnFrames) -> Callable[..., list[dict[str, Any]]]:
    """Feed one event of this session to the turn; the frames it adds."""

    def frames(kind: str, **properties: Any) -> list[dict[str, Any]]:
        return turn.frames(
            Event(type=kind, properties={"sessionID": SESSION, **properties})
        )

    return frames


def test_the_summary_is_not_streamed_as_the_reply() -> None:
    """The summary is opencode's note to itself, written while the user watches."""
    frames = _stream(TurnFrames(SESSION))

    frames("message.updated", info={"id": "u1", "role": "user"})
    frames(
        "message.updated",
        info={"id": "s1", "role": "assistant", "summary": True, "mode": "compaction"},
    )
    shown = frames(
        "message.part.updated",
        part={"id": "p1", "messageID": "s1", "type": "text", "text": ""},
    )
    shown += frames("message.part.delta", partID="p1", field="text", delta=SUMMARY)
    shown += frames(
        "message.part.updated",
        part={"id": "p1", "messageID": "s1", "type": "text", "text": SUMMARY},
    )
    frames("message.updated", info={"id": "a2", "role": "assistant"})
    shown += frames(
        "message.part.updated",
        part={"id": "p2", "messageID": "a2", "type": "text", "text": "Done."},
    )

    assert shown == [{"type": "delta", "text": "Done."}]


OVERFLOW = {
    "name": "ContextOverflowError",
    "data": {"message": "request (40000 tokens) exceeds the available context size"},
}


def test_an_overflow_opencode_compacts_away_is_not_an_error() -> None:
    """opencode reports the provider's refusal, then compacts, replays and answers."""
    frames = _stream(TurnFrames(SESSION))

    frames("message.updated", info={"id": "u1", "role": "user"})
    shown = frames("session.error", error=OVERFLOW)
    frames(
        "message.updated",
        info={"id": "s1", "role": "assistant", "summary": True, "mode": "compaction"},
    )
    frames("message.updated", info={"id": "r1", "role": "user"})
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown += frames(
        "message.part.updated",
        part={"id": "p1", "messageID": "a1", "type": "text", "text": "Done."},
    )

    assert shown == [{"type": "delta", "text": "Done."}]


def test_a_summary_that_failed_ends_the_turn_with_one_error() -> None:
    """Too long even to summarise: opencode marks the summary and says nothing else."""
    frames = _stream(TurnFrames(SESSION))
    summary = {"id": "s1", "role": "assistant", "summary": True, "mode": "compaction"}
    failed = {
        **summary,
        "finish": "error",
        "error": {
            "name": "ContextOverflowError",
            "data": {"message": "Conversation history too large to compact"},
        },
    }

    frames("message.updated", info={"id": "u1", "role": "user"})
    shown = frames("session.error", error=OVERFLOW)
    shown += frames("message.updated", info=summary)
    shown += frames("session.error", error=OVERFLOW)
    shown += frames("message.updated", info=failed)
    shown += frames("message.updated", info=failed)

    assert [frame["type"] for frame in shown] == ["error"]
    assert "start a new thread" in shown[0]["message"]


def test_a_summary_the_provider_failed_is_reported_once() -> None:
    """opencode publishes the provider's error, then marks the summary with it too."""
    frames = _stream(TurnFrames(SESSION))
    broken = {"name": "APIError", "data": {"message": "Internal server error"}}

    frames("message.updated", info={"id": "u1", "role": "user"})
    shown = frames("session.error", error=broken)
    shown += frames(
        "message.updated",
        info={
            "id": "s1",
            "role": "assistant",
            "summary": True,
            "mode": "compaction",
            "finish": "error",
            "error": broken,
        },
    )

    assert [frame["message"] for frame in shown] == ["Internal server error"]
