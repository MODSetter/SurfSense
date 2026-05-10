"""Unit tests for ``task_span`` open/close helpers."""

from __future__ import annotations

import pytest

from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import (
    clear_task_span_if_delegating_task_ended,
    ensure_pending_task_span_for_lc,
    open_task_span,
)

pytestmark = pytest.mark.unit


def test_open_task_span_sets_span_and_run_id() -> None:
    state = AgentEventRelayState.for_invocation()
    sid = open_task_span(state, run_id="run-abc")
    assert sid.startswith("spn_")
    assert state.active_span_id == sid
    assert state.active_task_run_id == "run-abc"
    assert state.span_metadata_if_active() == {"spanId": sid}


def test_clear_ignored_for_non_task_tool() -> None:
    state = AgentEventRelayState.for_invocation()
    open_task_span(state, run_id="run-1")
    sid = state.active_span_id
    clear_task_span_if_delegating_task_ended(
        state, tool_name="web_search", run_id="run-1"
    )
    assert state.active_span_id == sid
    assert state.active_task_run_id == "run-1"


def test_clear_ignored_when_task_run_id_mismatches() -> None:
    state = AgentEventRelayState.for_invocation()
    open_task_span(state, run_id="run-open")
    clear_task_span_if_delegating_task_ended(
        state, tool_name="task", run_id="run-other"
    )
    assert state.active_span_id is not None
    assert state.active_task_run_id == "run-open"


def test_clear_on_matching_task_end() -> None:
    state = AgentEventRelayState.for_invocation()
    open_task_span(state, run_id="run-x")
    clear_task_span_if_delegating_task_ended(state, tool_name="task", run_id="run-x")
    assert state.active_span_id is None
    assert state.active_task_run_id is None
    assert state.span_metadata_if_active() is None


def test_clear_noop_when_no_open_span() -> None:
    state = AgentEventRelayState.for_invocation()
    clear_task_span_if_delegating_task_ended(state, tool_name="task", run_id="run-x")
    assert state.active_span_id is None


def test_pending_then_open_reuses_same_span_id() -> None:
    state = AgentEventRelayState.for_invocation()
    sid_pending = ensure_pending_task_span_for_lc(state, "lc-task-1")
    assert state.pending_task_span_by_lc["lc-task-1"] == sid_pending
    sid_active = open_task_span(
        state, run_id="run-1", langchain_tool_call_id="lc-task-1"
    )
    assert sid_active == sid_pending
    assert state.active_span_id == sid_pending
    assert "lc-task-1" not in state.pending_task_span_by_lc
