"""Following a run: text frames already waiting go as one, in order, resumable from any id."""

import asyncio
import json

import pytest

from modules.agent.agent_threads.turn import _frame as agent_frame
from modules.chat.router import _frame as chat_frame
from modules.chat.runs.run import Run

pytestmark = pytest.mark.unit

REASONING = [f"r{n} " for n in range(200)]
ANSWER = ["abcd"] * 5000
AFTER_STEP = ["\u2028ok"] * 10


def _running_reply() -> Run:
    """A finished agent reply: its trace, the trace's end, text, a step, more text."""
    run = Run()
    run.add(
        chat_frame(
            {
                "type": "accepted",
                "user_message_id": 1,
                "assistant_message_id": 2,
                "user_created_at": None,
            }
        )
    )
    for text in REASONING:
        run.add(chat_frame({"type": "reasoning", "text": text}))
    run.add(chat_frame({"type": "reasoning-end", "duration_ms": 5}))
    for text in ANSWER:
        run.add(chat_frame({"type": "delta", "text": text}))
    run.add(
        agent_frame(
            {
                "type": "agent-step",
                "id": "s",
                "tool": "read",
                "status": "running",
                "title": None,
                "input": {},
            }
        )
    )
    for text in AFTER_STEP:
        run.add(agent_frame({"type": "delta", "text": text}))
    run.finish()
    return run


def _parsed(frames: list[bytes]) -> list[tuple[int, dict]]:
    """Each frame's id and payload, `[DONE]` as {"type": "done"}."""
    parsed = []
    for frame in frames:
        id_line, data_line = frame.decode().removesuffix("\n\n").split("\n")
        data = data_line.removeprefix("data: ")
        payload = {"type": "done"} if data == "[DONE]" else json.loads(data)
        parsed.append((int(id_line.removeprefix("id: ")), payload))
    return parsed


async def _followed(run: Run, after: int = 0) -> list[tuple[int, dict]]:
    return _parsed([frame async for frame in run.follow(after)])


def _text(events: list[tuple[int, dict]], kind: str) -> str:
    return "".join(event["text"] for _, event in events if event["type"] == kind)


async def test_a_late_follower_gets_each_run_of_text_as_one_frame() -> None:
    """5,213 frames replay as 7, never merged across a frame that is not text."""
    events = await _followed(_running_reply())

    assert [event["type"] for _, event in events] == [
        "accepted",
        "reasoning",
        "reasoning-end",
        "delta",
        "agent-step",
        "delta",
        "done",
    ]
    assert [frame_id for frame_id, _ in events] == [1, 201, 202, 5202, 5203, 5213, 5214]
    assert _text(events, "reasoning") == "".join(REASONING)
    assert _text(events, "delta") == "".join(ANSWER + AFTER_STEP)


async def test_resuming_from_any_id_sends_exactly_what_came_after_it() -> None:
    """An id inside a merged run, or the one a merged frame carried, loses and repeats nothing."""
    run = _running_reply()
    every = [(n, frame) for n, frame in enumerate(_parsed(run._frames), start=1)]

    for after in (0, 1, 2, 150, 201, 202, 203, 2500, 5202, 5203, 5210, 5213, 5214):
        events = await _followed(run, after)
        rest = [event for n, (_, event) in every if n > after]

        assert all(frame_id > after for frame_id, _ in events)
        ids = [frame_id for frame_id, _ in events]
        assert ids == sorted(set(ids))
        for kind in ("reasoning", "delta"):
            assert _text(events, kind) == "".join(
                event["text"] for event in rest if event["type"] == kind
            )
        assert [event["type"] for _, event in events if "text" not in event] == [
            event["type"] for event in rest if "text" not in event
        ]


async def test_a_waiting_follower_gets_a_new_frame_at_once() -> None:
    """Merging never holds a frame back to wait for the next one."""
    run = Run()
    received: list[bytes] = []

    async def follow() -> None:
        async for frame in run.follow():
            received.append(frame)

    following = asyncio.create_task(follow())
    await asyncio.sleep(0)
    run.add(chat_frame({"type": "delta", "text": "Hel"}))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert received == [b'id: 1\ndata: {"type": "delta", "text": "Hel"}\n\n']

    run.add(chat_frame({"type": "delta", "text": "lo"}))
    run.add(chat_frame({"type": "delta", "text": " there"}))
    run.finish()
    await following

    assert _parsed(received[1:]) == [
        (3, {"type": "delta", "text": "lo there"}),
        (4, {"type": "done"}),
    ]


async def test_a_text_frame_that_carries_more_than_text_is_never_merged() -> None:
    """Only a frame of `type` and `text` alone appends exactly what it says."""
    run = Run()
    run.add(chat_frame({"type": "delta", "text": "a"}))
    run.add(b'data: {"type": "delta", "text": "b", "part": 2}\n\n')
    run.add(chat_frame({"type": "delta", "text": "c"}))
    run.finish()

    events = await _followed(run)

    assert [event for _, event in events] == [
        {"type": "delta", "text": "a"},
        {"type": "delta", "text": "b", "part": 2},
        {"type": "delta", "text": "c"},
        {"type": "done"},
    ]
