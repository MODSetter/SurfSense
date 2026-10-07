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

    def frames(kind: str, **properties: Any) -> list[dict[str, Any]]:
        return turn.frames(
            Event(type=kind, properties={"sessionID": SESSION, **properties})
        )

    frames("message.updated", info={"id": "u1", "role": "user"})
    return frames


def _text_part(part_id: str, message_id: str, text: str = "") -> dict[str, Any]:
    return {"id": part_id, "messageID": message_id, "type": "text", "text": text}


def _tool_part(message_id: str) -> dict[str, Any]:
    return {
        "id": "t1",
        "messageID": message_id,
        "type": "tool",
        "tool": "read",
        "state": {"status": "completed", "input": {}, "output": "page 1"},
    }


def _shown(frames: list[dict[str, Any]]) -> str:
    return "".join(f["text"] for f in frames if f["type"] == "delta")


def test_text_after_a_tool_call_streams_as_a_new_paragraph() -> None:
    """opencode starts each step's text as its own part; the stream must not run them together."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames("message.part.updated", part=_text_part("p1", "a1"))
    shown += frames("message.part.delta", partID="p1", field="text", delta=BEFORE)
    shown += frames("message.part.updated", part=_tool_part("a1"))
    frames("message.updated", info={"id": "a2", "role": "assistant"})
    shown += frames("message.part.updated", part=_text_part("p2", "a2"))
    shown += frames("message.part.delta", partID="p2", field="text", delta="I've")
    shown += frames("message.part.delta", partID="p2", field="text", delta=AFTER[4:])
    shown += frames("message.part.updated", part=_text_part("p2", "a2", AFTER))

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_a_part_no_delta_carried_is_set_apart_too() -> None:
    """Text that arrives only in the part's update is caught up with the same break."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames("message.part.updated", part=_text_part("p1", "a1", BEFORE))
    shown += frames("message.part.updated", part=_text_part("p2", "a1", AFTER))

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_a_reply_in_one_part_streams_as_it_was_written() -> None:
    """Nothing is added before the first text, or inside a part."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames("message.part.updated", part=_text_part("p1", "a1"))
    shown += frames("message.part.delta", partID="p1", field="text", delta="Revenue ")
    shown += frames("message.part.delta", partID="p1", field="text", delta="rose.")

    assert shown == [
        {"type": "delta", "text": "Revenue "},
        {"type": "delta", "text": "rose."},
    ]


def test_reasoning_between_the_parts_does_not_count_as_text() -> None:
    """Only answer text is set apart; the thinking stream stays as it was."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames(
        "message.part.updated",
        part={"id": "r1", "messageID": "a1", "type": "reasoning", "text": "Hm."},
    )
    shown += frames("message.part.updated", part=_text_part("p1", "a1", AFTER))

    assert shown == [
        {"type": "reasoning", "text": "Hm."},
        {"type": "delta", "text": AFTER},
    ]


def test_blank_parts_and_breaks_around_tool_calls_leave_one_blank_line() -> None:
    """A rehearsal's reply streamed runs of empty lines: parts of only breaks, and parts led by them."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames("message.part.updated", part=_text_part("p1", "a1"))
    shown += frames("message.part.delta", partID="p1", field="text", delta="\n\n")
    shown += frames("message.part.updated", part=_tool_part("a1"))
    frames("message.updated", info={"id": "a2", "role": "assistant"})
    shown += frames("message.part.updated", part=_text_part("p2", "a2"))
    for delta in ("\n\n", BEFORE, "\n\n"):
        shown += frames("message.part.delta", partID="p2", field="text", delta=delta)
    frames("message.updated", info={"id": "a3", "role": "assistant"})
    shown += frames("message.part.updated", part=_text_part("p3", "a3"))
    for delta in ("\n\n", "\n\nI've", AFTER[4:], "\n"):
        shown += frames("message.part.delta", partID="p3", field="text", delta=delta)

    assert _shown(shown) == f"{BEFORE}\n\n{AFTER}"


def test_breaks_inside_a_part_still_stream_once_text_follows() -> None:
    """A code block's blank lines are the model's own, so only a part's ends are trimmed."""
    frames = _stream()
    frames("message.updated", info={"id": "a1", "role": "assistant"})
    shown = frames("message.part.updated", part=_text_part("p1", "a1"))
    for delta in ("```\nx = 1\n", "\n\n", "y = 2\n```"):
        shown += frames("message.part.delta", partID="p1", field="text", delta=delta)

    assert _shown(shown) == "```\nx = 1\n\n\ny = 2\n```"


def test_a_stored_reply_drops_parts_of_only_breaks() -> None:
    """The reopened thread reads as the stream did."""
    messages = _messages(
        [_text_part("p1", "a1", "\n\n"), _tool_part("a1")],
        [_text_part("p2", "a2", f"\n\n{BEFORE}\n\n")],
        [_text_part("p3", "a3", f"\n\n\n\n{AFTER}\n")],
    )

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def _messages(*assistant_parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A user message and one assistant message per list of parts."""
    return [
        {"info": {"id": "u1", "role": "user"}, "parts": []},
        *(
            {
                "info": {"id": f"a{n}", "role": "assistant", "parentID": "u1"},
                "parts": parts,
            }
            for n, parts in enumerate(assistant_parts, start=1)
        ),
    ]


def test_a_stored_reply_keeps_the_break_between_parts_of_one_message() -> None:
    """Text, a tool call and more text in one step read back as two paragraphs."""
    messages = _messages(
        [
            _text_part("p1", "a1", BEFORE),
            _tool_part("a1"),
            _text_part("p2", "a1", AFTER),
        ]
    )

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def test_a_stored_reply_across_steps_keeps_the_break() -> None:
    """The completed frame and the reopened thread say the same as the stream."""
    messages = _messages(
        [_text_part("p1", "a1", BEFORE), _tool_part("a1")],
        [_text_part("p2", "a2", AFTER)],
    )

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == f"{BEFORE}\n\n{AFTER}"


def test_a_stored_reply_in_one_part_is_unchanged() -> None:
    """Its own paragraphs stay as written."""
    messages = _messages([_text_part("p1", "a1", "Revenue rose.\n\nCosts fell.")])

    reply = turn_reply(messages, "u1", [])

    assert reply is not None
    assert reply["content"]["text"] == "Revenue rose.\n\nCosts fell."
