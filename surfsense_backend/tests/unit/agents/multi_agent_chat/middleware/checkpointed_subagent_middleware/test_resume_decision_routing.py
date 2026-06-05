"""Slicing helper that routes a flat decisions list to per-tool-call payloads.

The frontend submits ``decisions: list[ResumeDecision]`` in the same order the
SSE stream emitted approval cards. When multiple parallel subagents are paused,
the backend slices that flat list into per-``tool_call_id`` payloads so each
``atask`` reads only its own decisions through ``consume_surfsense_resume``.

The extractor reads ``state.interrupts[i].value["tool_call_id"]`` — which is
populated by ``propagation.wrap_with_tool_call_id`` inside ``task_tool``'s
``except GraphInterrupt`` chokepoint whenever a subagent interrupt bubbles up
through ``[a]task`` — to build the ordered ``pending`` list the slicer needs.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.resume_routing import (
    collect_pending_tool_calls,
    slice_decisions_by_tool_call,
)


class TestSliceDecisionsByToolCall:
    def test_splits_flat_decisions_across_two_pending_tool_calls(self):
        decisions = [
            {"type": "approve"},
            {"type": "edit", "edited_action": {"name": "edited-b1"}},
            {"type": "reject"},
            {"type": "approve"},
            {"type": "approve"},
        ]
        pending = [
            ("tcid-A", 3),
            ("tcid-B", 2),
        ]

        routed = slice_decisions_by_tool_call(decisions, pending)

        assert routed == {
            "tcid-A": {"decisions": decisions[0:3]},
            "tcid-B": {"decisions": decisions[3:5]},
        }

    def test_raises_when_decision_count_less_than_total_actions(self):
        decisions = [{"type": "approve"}, {"type": "approve"}]
        pending = [("tcid-A", 3), ("tcid-B", 2)]

        with pytest.raises(ValueError, match=r"5 actions.*2 decisions"):
            slice_decisions_by_tool_call(decisions, pending)

    def test_raises_when_decision_count_greater_than_total_actions(self):
        decisions = [{"type": "approve"}] * 6
        pending = [("tcid-A", 3), ("tcid-B", 2)]

        with pytest.raises(ValueError, match=r"5 actions.*6 decisions"):
            slice_decisions_by_tool_call(decisions, pending)

    def test_handles_single_pending_tool_call(self):
        decisions = [{"type": "approve"}, {"type": "reject"}]
        pending = [("tcid-only", 2)]

        routed = slice_decisions_by_tool_call(decisions, pending)

        assert routed == {"tcid-only": {"decisions": decisions}}

    def test_returns_empty_dict_for_no_pending(self):
        routed = slice_decisions_by_tool_call([], [])

        assert routed == {}


def _interrupt_with(tool_call_id: str, action_count: int):
    return SimpleNamespace(
        id=f"i-{tool_call_id}",
        value={
            "action_requests": [{"name": "n", "args": {}}] * action_count,
            "review_configs": [{}] * action_count,
            "tool_call_id": tool_call_id,
        },
    )


class TestCollectPendingToolCalls:
    def test_single_pending_returns_one_pair(self):
        state = SimpleNamespace(interrupts=(_interrupt_with("tcid-only", 3),))

        assert collect_pending_tool_calls(state) == [("tcid-only", 3)]

    def test_multiple_pending_preserves_state_order(self):
        """Order must match what the SSE stream emitted (= state.interrupts order)."""
        state = SimpleNamespace(
            interrupts=(
                _interrupt_with("tcid-A", 2),
                _interrupt_with("tcid-B", 3),
            )
        )

        assert collect_pending_tool_calls(state) == [("tcid-A", 2), ("tcid-B", 3)]

    def test_empty_when_no_interrupts(self):
        state = SimpleNamespace(interrupts=())

        assert collect_pending_tool_calls(state) == []

    def test_skips_interrupts_without_tool_call_id(self):
        """Defensive: interrupts not produced by our propagation layer are ignored.

        ``stream_resume_chat`` only owns the ``task``-routing slice; non-task
        interrupts (e.g. parent-side HITL middleware on a different tool) are
        not the slicer's responsibility.
        """
        state = SimpleNamespace(
            interrupts=(
                _interrupt_with("tcid-A", 2),
                SimpleNamespace(id="i-foreign", value={"action_requests": [{}]}),
                _interrupt_with("tcid-B", 1),
            )
        )

        assert collect_pending_tool_calls(state) == [("tcid-A", 2), ("tcid-B", 1)]

    def test_handles_scalar_value_interrupt(self):
        """Subagents using ``interrupt("approve?")`` style propagate as ``{"value": ..., "tool_call_id": ...}``.

        These have no ``action_requests`` — count them as a single action so
        the frontend submits exactly one decision per such interrupt.
        """
        state = SimpleNamespace(
            interrupts=(
                SimpleNamespace(
                    id="i-A",
                    value={"value": "approve?", "tool_call_id": "tcid-A"},
                ),
            )
        )

        assert collect_pending_tool_calls(state) == [("tcid-A", 1)]

    def test_raises_when_interrupt_value_missing_action_count_keys(self):
        """An interrupt with ``tool_call_id`` but no usable count signals a contract bug."""
        state = SimpleNamespace(
            interrupts=(
                SimpleNamespace(
                    id="i-A",
                    value={"tool_call_id": "tcid-A", "weird_shape": True},
                ),
            )
        )

        with pytest.raises(ValueError, match="action_requests"):
            collect_pending_tool_calls(state)
