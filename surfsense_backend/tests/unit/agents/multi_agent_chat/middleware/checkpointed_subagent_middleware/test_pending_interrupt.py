"""Pins the first-wins assumption of ``get_first_pending_subagent_interrupt``.

The bridge currently relies on at-most-one pending interrupt per snapshot
(sequential tool nodes). If parallel tool calls are ever enabled, the bridge
needs an id-aware lookup; these tests will need to be revisited at that point.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume import (
    get_first_pending_subagent_interrupt,
)


class TestGetFirstPendingSubagentInterrupt:
    def test_returns_first_when_multiple_top_level_interrupts_pending(self):
        first = SimpleNamespace(id="i-1", value={"decision": "approve"})
        second = SimpleNamespace(id="i-2", value={"decision": "reject"})
        state = SimpleNamespace(interrupts=(first, second), tasks=())

        assert get_first_pending_subagent_interrupt(state) == (
            "i-1",
            {"decision": "approve"},
        )

    def test_returns_first_when_multiple_subtask_interrupts_pending(self):
        first = SimpleNamespace(id="i-A", value="approve")
        second = SimpleNamespace(id="i-B", value="reject")
        sub_task = SimpleNamespace(interrupts=(first, second))
        state = SimpleNamespace(interrupts=(), tasks=(sub_task,))

        assert get_first_pending_subagent_interrupt(state) == ("i-A", "approve")

    def test_returns_none_when_no_interrupts(self):
        state = SimpleNamespace(interrupts=(), tasks=())

        assert get_first_pending_subagent_interrupt(state) == (None, None)

    def test_returns_none_when_state_is_none(self):
        assert get_first_pending_subagent_interrupt(None) == (None, None)

    def test_skips_interrupts_with_none_value(self):
        empty = SimpleNamespace(id="i-empty", value=None)
        real = SimpleNamespace(id="i-real", value="approve")
        state = SimpleNamespace(interrupts=(empty, real), tasks=())

        assert get_first_pending_subagent_interrupt(state) == ("i-real", "approve")

    def test_normalizes_non_string_id_to_none(self):
        interrupt = SimpleNamespace(id=12345, value="approve")
        state = SimpleNamespace(interrupts=(interrupt,), tasks=())

        assert get_first_pending_subagent_interrupt(state) == (None, "approve")
