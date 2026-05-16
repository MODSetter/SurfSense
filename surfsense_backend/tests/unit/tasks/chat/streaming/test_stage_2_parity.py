"""Parity tests for Stage 2 extractions (tool matching, thinking step, custom events)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.tasks.chat.stream_new_chat import _legacy_match_lc_id as old_legacy_match
from app.tasks.chat.streaming.handlers.custom_events import (
    handle_action_log,
    handle_action_log_updated,
    handle_document_created,
    handle_report_progress,
)
from app.tasks.chat.streaming.helpers.tool_call_matching import (
    match_buffered_langchain_tool_call_id as new_legacy_match,
)
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.thinking_step_completion import (
    complete_active_thinking_step,
)
from app.tasks.chat.streaming.relay.thinking_step_sse import emit_thinking_step_frame

pytestmark = pytest.mark.unit


def _copy_chunk_buffer(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(x) for x in raw]


def test_legacy_tool_call_match_matches_old_implementation() -> None:
    cases: list[tuple[list[dict[str, Any]], str, str, dict[str, str]]] = [
        (
            [
                {"name": "write_file", "id": "lc-a"},
                {"name": "other", "id": "lc-b"},
            ],
            "write_file",
            "run-1",
            {},
        ),
        (
            [{"name": "x", "id": None}, {"name": "y", "id": "lc-fallback"}],
            "write_file",
            "run-2",
            {},
        ),
        ([{"name": "no_id"}], "write_file", "run-3", {}),
    ]
    for chunks_template, tool_name, run_id, lc_map_seed in cases:
        old_chunks = _copy_chunk_buffer(chunks_template)
        new_chunks = _copy_chunk_buffer(chunks_template)
        old_map = dict(lc_map_seed)
        new_map = dict(lc_map_seed)
        old_out = old_legacy_match(old_chunks, tool_name, run_id, old_map)
        new_out = new_legacy_match(new_chunks, tool_name, run_id, new_map)
        assert new_out == old_out
        assert new_chunks == old_chunks
        assert new_map == old_map


def test_emit_thinking_step_frame_invokes_builder_before_service() -> None:
    order: list[str] = []
    builder = MagicMock()

    def on_ts(*args: Any, **kwargs: Any) -> None:
        order.append("builder")

    builder.on_thinking_step.side_effect = on_ts

    svc = MagicMock()

    def fmt(**kwargs: Any) -> str:
        order.append("service")
        return "frame"

    svc.format_thinking_step.side_effect = fmt

    out = emit_thinking_step_frame(
        streaming_service=svc,
        content_builder=builder,
        step_id="thinking-1",
        title="Working",
        status="in_progress",
        items=["a"],
    )
    assert out == "frame"
    assert order == ["builder", "service"]
    builder.on_thinking_step.assert_called_once()
    svc.format_thinking_step.assert_called_once()


def test_emit_thinking_step_frame_skips_builder_when_none() -> None:
    svc = MagicMock(return_value="x")
    svc.format_thinking_step.return_value = "frame"
    assert (
        emit_thinking_step_frame(
            streaming_service=svc,
            content_builder=None,
            step_id="s",
            title="t",
        )
        == "frame"
    )
    svc.format_thinking_step.assert_called_once()


def test_complete_active_thinking_step_mirrors_closure_semantics() -> None:
    svc = MagicMock()
    svc.format_thinking_step.return_value = "done-frame"
    completed: set[str] = set()
    relay_state = AgentEventRelayState.for_invocation()

    frame, new_id = complete_active_thinking_step(
        state=relay_state,
        streaming_service=svc,
        content_builder=None,
        last_active_step_id="thinking-1",
        last_active_step_title="T",
        last_active_step_items=["x"],
        completed_step_ids=completed,
    )
    assert frame == "done-frame"
    assert new_id is None
    assert "thinking-1" in completed

    frame2, id2 = complete_active_thinking_step(
        state=relay_state,
        streaming_service=svc,
        content_builder=None,
        last_active_step_id="thinking-1",
        last_active_step_title="T",
        last_active_step_items=[],
        completed_step_ids=completed,
    )
    assert frame2 is None
    assert id2 == "thinking-1"


def test_agent_event_relay_state_factory_matches_counter_rule() -> None:
    s0 = AgentEventRelayState.for_invocation()
    assert s0.thinking_step_counter == 0
    assert s0.last_active_step_id is None

    s1 = AgentEventRelayState.for_invocation(
        initial_step_id="thinking-resume-1",
        initial_step_title="Inherited",
        initial_step_items=["Topic: X"],
    )
    assert s1.thinking_step_counter == 1
    assert s1.last_active_step_id == "thinking-resume-1"
    assert s1.next_thinking_step_id("thinking") == "thinking-2"


@pytest.mark.parametrize(
    ("phase", "message", "start_items", "expected_tail"),
    [
        (
            "revising_section",
            "progress line",
            ["Topic: Foo", "Modifying bar", "stale..."],
            ["Topic: Foo", "Modifying bar", "progress line"],
        ),
        (
            "other",
            "phase msg",
            ["Topic: Foo", "old line"],
            ["Topic: Foo", "phase msg"],
        ),
    ],
)
def test_report_progress_items_match_reference(
    phase: str,
    message: str,
    start_items: list[str],
    expected_tail: list[str],
) -> None:
    svc = MagicMock()
    svc.format_thinking_step.return_value = "sse"

    items = list(start_items)
    frame, new_items = handle_report_progress(
        {"message": message, "phase": phase},
        last_active_step_id="step-1",
        last_active_step_title="Report",
        last_active_step_items=items,
        streaming_service=svc,
        content_builder=None,
    )
    assert frame == "sse"
    assert new_items == expected_tail
    kwargs = svc.format_thinking_step.call_args.kwargs
    assert kwargs["items"] == expected_tail


def test_report_progress_noop_when_missing_message_or_step() -> None:
    svc = MagicMock()
    items = ["Topic: A"]
    f1, i1 = handle_report_progress(
        {"message": "", "phase": "x"},
        last_active_step_id="s",
        last_active_step_title="t",
        last_active_step_items=items,
        streaming_service=svc,
        content_builder=None,
    )
    assert f1 is None and i1 is items

    f2, i2 = handle_report_progress(
        {"message": "m", "phase": "x"},
        last_active_step_id=None,
        last_active_step_title="t",
        last_active_step_items=items,
        streaming_service=svc,
        content_builder=None,
    )
    assert f2 is None and i2 is items


def test_document_action_handlers_match_format_data_guards() -> None:
    svc = MagicMock()
    svc.format_data.return_value = "data-frame"

    assert handle_document_created({}, streaming_service=svc) is None
    assert handle_document_created({"id": 0}, streaming_service=svc) is None
    handle_document_created({"id": 42, "title": "x"}, streaming_service=svc)
    svc.format_data.assert_called_with(
        "documents-updated", {"action": "created", "document": {"id": 42, "title": "x"}}
    )

    svc.reset_mock()
    assert handle_action_log({"id": None}, streaming_service=svc) is None
    handle_action_log({"id": 1}, streaming_service=svc)
    svc.format_data.assert_called_once_with("action-log", {"id": 1})

    svc.reset_mock()
    assert handle_action_log_updated({"id": None}, streaming_service=svc) is None
    handle_action_log_updated({"id": 2}, streaming_service=svc)
    svc.format_data.assert_called_once_with("action-log-updated", {"id": 2})
