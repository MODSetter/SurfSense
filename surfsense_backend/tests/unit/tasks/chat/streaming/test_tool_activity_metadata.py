"""Unit tests for ``AgentEventRelayState.tool_activity_metadata``."""

from __future__ import annotations

import pytest

from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import open_task_span

pytestmark = pytest.mark.unit


def test_returns_none_when_no_span_and_no_thinking_step() -> None:
    state = AgentEventRelayState.for_invocation()
    assert state.tool_activity_metadata(thinking_step_id=None) is None
    assert state.tool_activity_metadata(thinking_step_id="") is None
    assert state.tool_activity_metadata(thinking_step_id="   ") is None


def test_thinking_step_id_only() -> None:
    state = AgentEventRelayState.for_invocation()
    assert state.tool_activity_metadata(thinking_step_id="thinking-3") == {
        "thinkingStepId": "thinking-3",
    }


def test_span_only_when_active() -> None:
    state = AgentEventRelayState.for_invocation()
    open_task_span(state, run_id="run-x")
    assert state.tool_activity_metadata(thinking_step_id=None) == {
        "spanId": state.active_span_id,
    }


def test_merges_span_and_thinking_step_when_both_set() -> None:
    state = AgentEventRelayState.for_invocation()
    open_task_span(state, run_id="run-x")
    md = state.tool_activity_metadata(thinking_step_id="thinking-7")
    assert md == {
        "spanId": state.active_span_id,
        "thinkingStepId": "thinking-7",
    }
