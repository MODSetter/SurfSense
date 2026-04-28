"""Tests for SpillToBackendEdit and SpillingContextEditingMiddleware."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.new_chat.middleware.context_editing import (
    SpillToBackendEdit,
    _build_spill_placeholder,
)

pytestmark = pytest.mark.unit


def _build_history(num_pairs: int = 6) -> list[Any]:
    """Build a long history of (AIMessage with tool_call, ToolMessage) pairs."""
    msgs: list[Any] = [HumanMessage(content="please do many things")]
    for i in range(num_pairs):
        msgs.append(
            AIMessage(
                content="",
                tool_calls=[
                    {"name": f"tool_{i}", "args": {"i": i}, "id": f"call-{i}"},
                ],
            )
        )
        msgs.append(
            ToolMessage(
                content="x" * 5000,
                tool_call_id=f"call-{i}",
                name=f"tool_{i}",
                id=f"tool-msg-{i}",
            )
        )
    return msgs


def _approx_count(messages: list[Any]) -> int:
    """Trivial token counter: 1 token per 4 chars."""
    total = 0
    for msg in messages:
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            total += len(content) // 4
    return total


class TestSpillEdit:
    def test_below_trigger_does_nothing(self) -> None:
        edit = SpillToBackendEdit(trigger=1_000_000, keep=2)
        msgs = _build_history(3)
        original_lengths = [len(getattr(m, "content", "")) for m in msgs]
        edit.apply(msgs, count_tokens=_approx_count)
        new_lengths = [len(getattr(m, "content", "")) for m in msgs]
        assert original_lengths == new_lengths
        assert edit.pending_spills == []

    def test_above_trigger_clears_and_records(self) -> None:
        edit = SpillToBackendEdit(trigger=100, keep=1, path_prefix="/tool_outputs")
        msgs = _build_history(4)
        edit.apply(msgs, count_tokens=_approx_count)

        # The most-recent ToolMessage (keep=1) should remain intact
        tool_messages = [m for m in msgs if isinstance(m, ToolMessage)]
        intact = tool_messages[-1]
        assert intact.content.startswith("x")  # untouched

        # Earlier ToolMessages should now contain the placeholder text
        cleared = [
            m for m in tool_messages
            if isinstance(m.content, str) and m.content.startswith("[cleared")
        ]
        assert len(cleared) >= 1
        # And the spill list should match
        assert len(edit.pending_spills) == len(cleared)

    def test_excluded_tools_not_cleared(self) -> None:
        edit = SpillToBackendEdit(
            trigger=100,
            keep=0,
            exclude_tools=("tool_0",),
        )
        msgs = _build_history(4)
        edit.apply(msgs, count_tokens=_approx_count)

        first_tool = next(
            m for m in msgs if isinstance(m, ToolMessage) and m.name == "tool_0"
        )
        # Excluded — untouched
        assert first_tool.content.startswith("x")

    def test_drain_clears_pending(self) -> None:
        edit = SpillToBackendEdit(trigger=100, keep=1)
        msgs = _build_history(4)
        edit.apply(msgs, count_tokens=_approx_count)
        first_drain = edit.drain_pending()
        assert len(first_drain) > 0
        assert edit.drain_pending() == []

    def test_placeholder_format(self) -> None:
        path = "/tool_outputs/thread-1/tool-msg-0.txt"
        text = _build_spill_placeholder(path)
        assert path in text
        assert "explore" in text  # mentions the recovery agent
