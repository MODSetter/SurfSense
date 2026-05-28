"""Lock ``build_auto_decisions`` — the HITL auto-approve/reject wire mapper.

``build_auto_decisions`` walks ``state.interrupts`` (duck-typed) and produces
two parallel resume maps: one keyed by LangGraph ``Interrupt.id`` and one
keyed by ``tool_call_id`` for the subagent middleware bridge. Both carry
the same decision payload.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.automations.actions.agent_task.auto_decide import build_auto_decisions

pytestmark = pytest.mark.unit


def _state(interrupts: list[Any]) -> SimpleNamespace:
    """Build a duck-typed LangGraph state stub carrying ``interrupts``."""
    return SimpleNamespace(interrupts=interrupts)


def _interrupt(*, id_: str, value: Any) -> SimpleNamespace:
    """Build a duck-typed interrupt with the canonical ``(id, value)`` shape."""
    return SimpleNamespace(id=id_, value=value)


def test_build_auto_decisions_produces_one_decision_per_action_request() -> None:
    """An interrupt carrying N ``action_requests`` produces N decisions of
    the requested type in both maps. This is the canonical batched-HITL
    wire shape — losing a decision would leave a pending action stuck."""
    interrupt = _interrupt(
        id_="lg-1",
        value={
            "tool_call_id": "tc-1",
            "action_requests": [{"id": "a"}, {"id": "b"}],
        },
    )

    lg_map, routed = build_auto_decisions(_state([interrupt]), "approve")

    assert lg_map == {"lg-1": {"decisions": [{"type": "approve"}, {"type": "approve"}]}}
    assert routed == {"tc-1": {"decisions": [{"type": "approve"}, {"type": "approve"}]}}


def test_build_auto_decisions_defaults_to_one_decision_for_scalar_interrupt() -> None:
    """When an interrupt's value has no ``action_requests`` list, the
    function defaults to a single decision. Locks compatibility with
    older single-action interrupt shapes still emitted by some tools."""
    interrupt = _interrupt(id_="lg-2", value={"tool_call_id": "tc-2"})

    lg_map, routed = build_auto_decisions(_state([interrupt]), "reject")

    assert lg_map == {"lg-2": {"decisions": [{"type": "reject"}]}}
    assert routed == {"tc-2": {"decisions": [{"type": "reject"}]}}


def test_build_auto_decisions_skips_interrupts_with_invalid_shape() -> None:
    """Interrupts missing the canonical ``(str id, dict value)`` shape are
    skipped silently rather than crashing the resume loop. Locks the
    resilience contract — a malformed interrupt from a misbehaving tool
    shouldn't take down the whole agent_task step."""
    good = _interrupt(id_="lg-good", value={"tool_call_id": "tc-good"})
    bad_value = _interrupt(id_="lg-bad-value", value="not a dict")
    bad_id = _interrupt(id_=None, value={"tool_call_id": "tc-bad-id"})  # type: ignore[arg-type]

    lg_map, routed = build_auto_decisions(_state([good, bad_value, bad_id]), "approve")

    assert lg_map == {"lg-good": {"decisions": [{"type": "approve"}]}}
    assert routed == {"tc-good": {"decisions": [{"type": "approve"}]}}
