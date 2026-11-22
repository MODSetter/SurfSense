"""A turn opencode compacted partway: the user's message and the agent's answer, without opencode's own notes.

The message shapes are opencode 2.1.2's: a compaction is a message of its own
(schema/src/session-message.ts). A thread from 1.x is read back as 2.x imports
it (core/src/database/v1-migration.bun.ts): its summary becomes that message, and
the "Continue…" or the user's message sent again stays after it.
"""

from collections.abc import Callable
from typing import Any

import pytest

from modules.agent.agent_threads import replies
from modules.agent.agent_threads.replies import thread_turns, turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.opencode_client import Event

pytestmark = pytest.mark.unit

SESSION = "ses_1"
SUMMARY = "## Objective\nDraft the proposal."


def _user(message_id: str, text: str | None = None) -> dict[str, Any]:
    return {
        "id": message_id,
        "type": "user",
        "text": text or f"Asked in {message_id}",
        "time": {"created": 1},
    }


def _assistant(message_id: str, text: str = "", **fields: Any) -> dict[str, Any]:
    return {
        "id": message_id,
        "type": "assistant",
        "content": [{"type": "text", "text": text}] if text else [],
        "time": {"created": 2, "completed": 3},
        "finish": "stop",
        **fields,
    }


def _compaction(message_id: str, status: str = "completed") -> dict[str, Any]:
    compaction: dict[str, Any] = {
        "id": message_id,
        "type": "compaction",
        "status": status,
        "reason": "auto",
        "time": {"created": 2},
    }
    if status == "completed":
        compaction["summary"] = SUMMARY
    else:
        compaction["error"] = TOO_LONG
    return compaction


def _idle(message_id: str, outcome: str = "succeeded", **fields: Any) -> dict[str, Any]:
    return {"id": message_id, "type": "idle", "outcome": outcome, **fields}


TOO_LONG = {
    "type": "compaction.failed",
    "message": "Compaction summary did not match the required template",
}
# 1.x's own note after a compaction, imported as a synthetic message.
CONTINUE = {
    "id": "k1",
    "type": "synthetic",
    "text": "Continue if you have next steps, or stop and ask for clarification "
    "if you are unsure how to proceed.",
    "time": {"created": 2},
}


def _shown(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(t["role"], t["content"]["text"]) for t in thread_turns(messages, [])]


def test_the_answer_after_a_compaction_is_the_turns_reply() -> None:
    """The summary is opencode's note to itself; the steps on either side are the reply."""
    messages = [
        _user("u1"),
        _assistant("a1", "Reading.", finish="tool-calls"),
        _compaction("c1"),
        _assistant("a2", "The proposal is in Studio."),
        _idle("i1"),
    ]

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == "Reading.\n\nThe proposal is in Studio."
    assert "ending" not in reply["content"]


def test_a_turn_compacted_by_1x_reads_back_as_one() -> None:
    """1.x's "Continue…" after its summary is not the user's."""
    messages = [
        _user("u1"),
        _assistant("a1", finish="tool-calls"),
        _compaction("c1"),
        CONTINUE,
        _assistant("a2", "The proposal is in Studio."),
    ]

    assert _shown(messages) == [
        ("user", "Asked in u1"),
        ("assistant", "The proposal is in Studio."),
    ]


def test_a_turn_1x_replayed_after_an_overflow_stays_one_turn() -> None:
    """1.x compacted a request too large for the provider and sent the user's message again."""
    messages = [
        _user("u1"),
        _compaction("c1"),
        _user("r1", "Asked in u1"),
        _assistant("a1", "Done."),
    ]

    assert _shown(messages) == [("user", "Asked in u1"), ("assistant", "Done.")]


def test_after_a_failed_compaction_the_next_message_is_the_users() -> None:
    """A compaction that failed ends the turn; nothing carries it on."""
    messages = [
        _user("u1"),
        _compaction("c1", "failed"),
        _idle("i1", "failed", error=TOO_LONG),
        _user("u2", "Asked in u1"),
        _assistant("a2", "Here it is."),
        _idle("i2"),
    ]

    assert _shown(messages) == [
        ("user", "Asked in u1"),
        ("user", "Asked in u1"),
        ("assistant", "Here it is."),
    ]


def test_a_turn_that_failed_after_its_steps_says_the_conversation_is_too_long() -> None:
    """Read back, it ends as the live turn did: the thread cannot go on."""
    reply = turn_reply(
        [
            _user("u1"),
            _assistant("a1", "Reading.", finish="tool-calls"),
            _compaction("c1", "failed"),
            _idle("i1", "failed", error=TOO_LONG),
        ],
        "u1",
        [],
    )

    assert reply is not None
    assert reply["content"]["ending"]["type"] == "error"
    assert "start a new thread" in reply["content"]["ending"]["message"]


MIXED = [
    _user("u0"),
    _assistant("a0", "First."),
    _idle("i0"),
    _user("u1"),
    _assistant("a1", finish="tool-calls"),
    _compaction("c1"),
    _assistant("a2", "The proposal is in Studio."),
    _idle("i1"),
    _user("u2"),
    _compaction("c2"),
    _assistant("a3", "Done."),
    _idle("i2"),
    _user("u3"),
    _compaction("c3", "failed"),
    _idle("i3", "failed", error=TOO_LONG),
    _user("u4"),
    _assistant("a4", "Step one.", finish="tool-calls"),
    _assistant("a5", "Step two."),
    _idle("i4", "interrupted"),
    _user("u5"),
]


@pytest.mark.parametrize("answering", [False, True])
def test_the_threads_replies_are_each_turns_own(answering: bool) -> None:
    """Read whole or a turn at a time, through compactions clean and failed."""
    noted = {"u4:reply": {"type": "stopped"}}

    turns = thread_turns(MIXED, [], noted, answering)

    users = [turn["id"] for turn in turns if turn["role"] == "user"]
    assert users == ["u0", "u1", "u2", "u3", "u4", "u5"]
    expected = [
        reply
        for user in users
        if (
            reply := turn_reply(
                MIXED, user, [], noted, live=answering and user == users[-1]
            )
        )
        is not None
    ]
    assert [turn for turn in turns if turn["role"] == "assistant"] == expected
    assert [reply["content"]["text"] for reply in expected] == [
        "First.",
        "The proposal is in Studio.",
        "Done.",
        "Step one.\n\nStep two.",
    ]
    assert expected[-1]["content"]["ending"] == {"type": "stopped"}


def test_a_thread_is_read_once_however_many_turns_it_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding each turn's steps by a pass per turn grew with turns times messages."""
    reads: list[int] = []
    grouped = replies.session_turns

    def counted(messages: list[dict[str, Any]]) -> list[replies.Turn]:
        reads.append(len(messages))
        return grouped(messages)

    monkeypatch.setattr(replies, "session_turns", counted)

    thread_turns(MIXED, [])

    assert reads == [len(MIXED)]


def _stream(turn: TurnFrames) -> Callable[..., list[dict[str, Any]]]:
    """Feed one event of this session to a turn that has begun; the frames it adds."""

    def frames(kind: str, **data: Any) -> list[dict[str, Any]]:
        return turn.frames(Event(type=kind, data={"sessionID": SESSION, **data}))

    frames("session.inbox.enqueued", inboxID="u1", item={"type": "user"})
    return frames


def _said(frames: Callable[..., list[dict[str, Any]]], step: str, text: str) -> list:
    shown = frames("session.text.started", assistantMessageID=step, ordinal=0)
    shown += frames(
        "session.text.delta", assistantMessageID=step, ordinal=0, delta=text
    )
    return shown + frames(
        "session.text.ended", assistantMessageID=step, ordinal=0, text=text
    )


def test_the_summary_is_not_streamed_as_the_reply() -> None:
    """The summary is opencode's note to itself, written while the user watches."""
    frames = _stream(TurnFrames(SESSION))

    shown = frames("session.compaction.started", reason="auto")
    shown += frames("session.compaction.delta", text=SUMMARY)
    shown += frames("session.compaction.ended", reason="auto", text=SUMMARY)
    shown += _said(frames, "a2", "Done.")

    assert shown == [{"type": "delta", "text": "Done."}]


OVERFLOW = {
    "type": "provider.invalid-request",
    "message": "request (40000 tokens) exceeds the available context size",
}


def test_an_overflow_opencode_compacts_away_is_not_an_error() -> None:
    """opencode fails the step, compacts, and answers in a new one."""
    frames = _stream(TurnFrames(SESSION))

    shown = frames("session.step.failed", assistantMessageID="a1", error=OVERFLOW)
    shown += frames("session.compaction.started", reason="auto")
    shown += frames("session.compaction.ended", reason="auto", text=SUMMARY)
    shown += _said(frames, "a2", "Done.")
    shown += frames("session.execution.succeeded")

    assert shown == [{"type": "delta", "text": "Done."}]


def test_a_compaction_that_failed_ends_the_turn_with_one_error() -> None:
    """Too long even to summarise: the conversation cannot go on."""
    frames = _stream(TurnFrames(SESSION))

    shown = frames("session.step.failed", assistantMessageID="a1", error=OVERFLOW)
    shown += frames("session.compaction.failed", reason="auto", error=TOO_LONG)
    shown += frames("session.execution.failed", error=TOO_LONG)

    assert [frame["type"] for frame in shown] == ["error"]
    assert "start a new thread" in shown[0]["message"]


def test_a_provider_failure_is_reported_once() -> None:
    """opencode fails the step, then the turn, with the same error."""
    frames = _stream(TurnFrames(SESSION))
    broken = {"type": "provider.error", "message": "Internal server error"}

    shown = frames("session.step.failed", assistantMessageID="a1", error=broken)
    shown += frames("session.execution.failed", error=broken)

    assert [frame["message"] for frame in shown] == ["Internal server error"]
