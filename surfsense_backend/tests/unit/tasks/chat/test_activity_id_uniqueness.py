"""Pin: canonical activity IDs must be globally unique within a thread.

Two consecutive resume turns must not emit overlapping activity IDs.

The contract this module pins: each ``stream_agent_events`` invocation must
receive a ``step_prefix`` that is unique within the thread (we salt with the
per-turn ``turn_id``), so the resulting activity IDs across consecutive turns
are always disjoint.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.agent.event_loop import (
    stream_agent_events as _stream_agent_events,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.tasks.chat.streaming.shared.utils import (
    resume_step_prefix as _resume_step_prefix,
)

pytestmark = pytest.mark.unit


@dataclass
class _FakeChunk:
    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)


class _FakeAgentState:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.tasks: list[Any] = []


class _FakeAgent:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._state = _FakeAgentState()

    async def astream_events(  # type: ignore[no-untyped-def]
        self, _input_data: Any, *, config: dict[str, Any], version: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        del config, version
        for ev in self._events:
            yield ev

    async def aget_state(self, _config: dict[str, Any]) -> _FakeAgentState:
        return self._state


def _tool_start(*, name: str, run_id: str) -> dict[str, Any]:
    return {
        "event": "on_tool_start",
        "name": name,
        "run_id": run_id,
        "data": {"input": {}},
    }


async def _drain_activity_ids(
    events: list[dict[str, Any]], *, step_prefix: str
) -> set[str]:
    """Run once and return every emitted activity ID."""
    agent = _FakeAgent(events)
    service = VercelStreamingService()
    result = StreamResult()
    config = {"configurable": {"thread_id": "regression-thread"}}

    sse_lines: list[str] = []
    async for sse in _stream_agent_events(
        agent, config, {}, service, result, step_prefix=step_prefix
    ):
        sse_lines.append(sse)

    ids: set[str] = set()
    for line in sse_lines:
        if not line.startswith("data: "):
            continue
        body = line[len("data: ") :].rstrip("\n")
        if not body or body == "[DONE]":
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "data-activity":
            continue
        activity_id = (payload.get("data") or {}).get("id")
        if isinstance(activity_id, str):
            ids.add(activity_id)
    return ids


@pytest.mark.asyncio
async def test_consecutive_invocations_with_same_prefix_produce_overlapping_activity_ids():
    """Pin the bug: identical ``step_prefix`` across two turns reuses ``-1``, ``-2``…

    This is what production was doing for resume — every resume invocation
    passed the same ``step_prefix`` and the relay state's counter
    restarted at 0. Two scrollback timelines built from such turns then
    presented React with siblings keyed by the same activity ID.
    """
    events = [
        _tool_start(name="t1", run_id="run-A-1"),
        _tool_start(name="t2", run_id="run-A-2"),
    ]

    ids_turn_one = await _drain_activity_ids(events, step_prefix="resume-constant")
    ids_turn_two = await _drain_activity_ids(events, step_prefix="resume-constant")

    assert ids_turn_one == ids_turn_two != set(), (
        "fixture broken: expected non-empty overlapping ids when prefix is reused"
    )


@pytest.mark.asyncio
async def test_per_turn_salted_prefix_yields_disjoint_activity_ids_across_turns():
    """The fix: salting the prefix with the per-turn ``turn_id`` makes IDs disjoint.

    Two consecutive resume calls in the same thread feed two different
    ``turn_id``s into the prefix, so the resulting activity IDs cannot collide
    no matter how many times the FE rehydrates from earlier assistant
    messages — which is the precondition for the React duplicate-key warning.
    """
    events = [
        _tool_start(name="t1", run_id="run-A-1"),
        _tool_start(name="t2", run_id="run-A-2"),
    ]

    ids_turn_one = await _drain_activity_ids(
        events, step_prefix="resume-104:1778698228472"
    )
    ids_turn_two = await _drain_activity_ids(
        events, step_prefix="resume-104:1778698244022"
    )

    assert ids_turn_one and ids_turn_two, "fixture broken: expected non-empty id sets"
    assert ids_turn_one.isdisjoint(ids_turn_two), (
        f"REGRESSION: per-turn-salted prefixes produced overlapping activity IDs: "
        f"{ids_turn_one & ids_turn_two!r}"
    )


def test_resume_step_prefix_helper_includes_turn_id_verbatim():
    """Production call-site pin: ``stream_resume_chat`` builds the prefix via
    this helper. Reverting it back to a hardcoded prefix would
    silently re-introduce the duplicate-key React warning across consecutive
    resumes — this test fails first instead.
    """
    a = _resume_step_prefix("104:1778698228472")
    b = _resume_step_prefix("104:1778698244022")

    assert a.startswith("resume-")
    assert "104:1778698228472" in a and "104:1778698244022" in b
    assert a != b
