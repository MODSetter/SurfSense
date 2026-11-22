"""A reply the agent writes in pieces, around its tool calls, reads as paragraphs, live and stored."""

from collections.abc import Callable
from typing import Any

import pytest

from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.opencode_client import Event

pytestmark = pytest.mark.unit

SESSION = "ses_1"
BEFORE = "The Context paragraph still spills onto page 2."
AFTER = "I've switched the chart to a line chart."


def _stream() -> Callable[..., list[dict[str, Any]]]:
    """Feed one event of this session to a turn that has begun; the frames it adds."""
    turn = TurnFrames(SESSION)

    def frames(kind: str, **data: Any) -> list[dict[str, Any]]:
        return turn.frames(Event(type=kind, data={"sessionID": SESSION, **data}))

    frames("session.inbox.enqueued", inboxID="u1", item={"type": "user"})
    return frames


def _text(frames: Callable[..., list], step: str, ordinal: int) -> Callable[..., list]:
    """The events of one text item: `started`, then each delta, or `ended` with the whole."""

    def item(*deltas: str, whole: str | None = None) -> list[dict[str, Any]]:
        where = {"assistantMessageID": step, "ordinal": ordinal}
        shown = frames("session.text.started", **where)
        for delta in deltas:
            shown += frames("session.text.delta", **where, delta=delta)
        if whole is not None:
            shown += frames("session.text.ended", **where, text=whole)
        return shown

    return item


def _tool(frames: Callable[..., list], step: str) -> list[dict[str, Any]]:
    """A read that answered, between two items of text."""
    where = {"assistantMessageID": step, "id": "call_1"}
    shown = frames("session.tool.input.started", **where, name="read")
    shown += frames("session.tool.called", **where, input={}, executed=False)
    return shown + frames(
        "session.tool.success",
        **where,
        content=[{"type": "text", "text": "page 1"}],
        executed=False,
    )


def _shown(frames: list[dict[str, Any]]) -> str:
    return "".join(f["text"] for f in frames if f["type"] == "delta")


def test_text_after_a_tool_call_streams_as_a_new_paragraph() -> None:
    """opencode starts each step's text as its own item; the stream must not run them together."""
    frames = _stream()
    shown = _text(frames, "a1", 0)(BEFORE)
    shown += _tool(frames, "a1")
    shown += _text(frames, "a2", 0)("I've", AFTER[4:], whole=AFTER)

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_an_item_no_delta_carried_is_set_apart_too() -> None:
    """Text that arrives only when its item ends is caught up with the same break."""
    frames = _stream()
    shown = _text(frames, "a1", 0)(whole=BEFORE)
    shown += _text(frames, "a1", 1)(whole=AFTER)

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_a_reply_in_one_item_streams_as_it_was_written() -> None:
    """Nothing is added before the first text, or inside an item."""
    frames = _stream()
    shown = _text(frames, "a1", 0)("Revenue ", "rose.")

    assert shown == [
        {"type": "delta", "text": "Revenue "},
        {"type": "delta", "text": "rose."},
    ]


def test_reasoning_between_the_items_does_not_count_as_text() -> None:
    """Only answer text is set apart; the thinking stream stays as it was."""
    frames = _stream()
    where = {"assistantMessageID": "a1", "ordinal": 0}
    shown = frames("session.reasoning.started", **where)
    shown += frames("session.reasoning.delta", **where, delta="Hm.")
    shown += _text(frames, "a1", 1)(whole=AFTER)

    assert shown == [
        {"type": "reasoning", "text": "Hm."},
        {"type": "delta", "text": AFTER},
    ]


def test_thinking_says_once_how_long_it_took() -> None:
    """Claude Code reports a thinking block's end twice: as it streams, and whole."""
    turn = TurnFrames(SESSION)

    def event(kind: str, created: int, **data: Any) -> Event:
        return Event(type=kind, created=created, data={"sessionID": SESSION, **data})

    where = {"assistantMessageID": "a1", "ordinal": 0}
    turn.frames(event("session.inbox.enqueued", 0, inboxID="u1", item={"type": "user"}))
    turn.frames(event("session.reasoning.started", 1_000, **where))
    ended = event("session.reasoning.ended", 3_500, **where, text="Hm.")

    shown = turn.frames(ended) + turn.frames(ended)

    assert shown == [
        {"type": "reasoning", "text": "Hm."},
        {"type": "reasoning-end", "duration_ms": 2_500},
    ]


def test_blank_items_and_breaks_around_tool_calls_leave_one_blank_line() -> None:
    """A rehearsal's reply streamed runs of empty lines: items of only breaks, and items led by them."""
    frames = _stream()
    shown = _text(frames, "a1", 0)("\n\n")
    shown += _tool(frames, "a1")
    shown += _text(frames, "a2", 0)("\n\n", BEFORE, "\n\n")
    shown += _text(frames, "a3", 0)("\n\n", "\n\nI've", AFTER[4:], "\n")

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_breaks_inside_an_item_still_stream_once_text_follows() -> None:
    """A code block's blank lines are the model's own, so only an item's ends are trimmed."""
    frames = _stream()
    shown = _text(frames, "a1", 0)("```\nx = 1\n", "\n\n", "y = 2\n```")

    assert _shown(shown) == "```\nx = 1\n\n\ny = 2\n```"


def _text_item(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _tool_item() -> dict[str, Any]:
    return {
        "type": "tool",
        "id": "call_1",
        "name": "read",
        "state": {
            "status": "completed",
            "input": {},
            "content": [{"type": "text", "text": "page 1"}],
        },
    }


def _messages(*steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A user message and one assistant message per list of items."""
    return [
        {"id": "u1", "type": "user", "text": "Fix it"},
        *(
            {"id": f"a{n}", "type": "assistant", "content": content}
            for n, content in enumerate(steps, start=1)
        ),
    ]


def test_a_stored_reply_drops_items_of_only_breaks() -> None:
    """The reopened thread reads as the stream did."""
    messages = _messages(
        [_text_item("\n\n"), _tool_item()],
        [_text_item(f"\n\n{BEFORE}\n\n")],
        [_text_item(f"\n\n\n\n{AFTER}\n")],
    )

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def test_a_stored_reply_keeps_the_break_between_items_of_one_step() -> None:
    """Text, a tool call and more text in one step read back as two paragraphs."""
    messages = _messages([_text_item(BEFORE), _tool_item(), _text_item(AFTER)])

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def test_a_stored_reply_across_steps_keeps_the_break() -> None:
    """The completed frame and the reopened thread say the same as the stream."""
    messages = _messages([_text_item(BEFORE), _tool_item()], [_text_item(AFTER)])

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def test_a_stored_reply_in_one_item_is_unchanged() -> None:
    """Its own paragraphs stay as written."""
    messages = _messages([_text_item("Revenue rose.\n\nCosts fell.")])

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == "Revenue rose.\n\nCosts fell."


# How opencode reports a reply the relay ended early, and one a plan refused mid-turn.
_CUT_OFF = {"type": "provider.unknown", "message": "The reply stopped early."}
_PLAN_LIMIT = {
    "type": "provider.error",
    "message": "Your ChatGPT plan's limit is reached.",
    "status": 403,
    "response": {
        "body": '{"error": {"message": "limit", "code": "subscription_limit"}}'
    },
}


@pytest.mark.parametrize(
    ("error", "kind"), [(_CUT_OFF, "unknown"), (_PLAN_LIMIT, "subscription_limit")]
)
def test_a_reply_that_fails_after_held_breaks_ends_on_its_error(
    error: dict[str, Any], kind: str
) -> None:
    """The breaks held at an item's end never follow the error, and the stored reply agrees."""
    frames = _stream()
    shown = _text(frames, "a1", 0)(BEFORE, "\n\n", whole=f"{BEFORE}\n\n")
    shown += frames("session.step.failed", assistantMessageID="a1", error=error)
    shown += frames("session.execution.failed", error=error)

    assert _shown(shown) == BEFORE
    assert [(f["type"], f.get("kind")) for f in shown] == [
        ("delta", None),
        ("error", kind),
    ]
    stored = [
        *_messages([_text_item(f"{BEFORE}\n\n")]),
        {"id": "i1", "type": "idle", "outcome": "failed", "error": error},
    ]
    stored[1] |= {"time": {"created": 2, "completed": 3}, "error": error}
    reply = turn_reply(stored, "u1", [])
    assert reply is not None
    assert reply["content"]["text"] == BEFORE
    assert reply["content"]["ending"]["kind"] == kind
