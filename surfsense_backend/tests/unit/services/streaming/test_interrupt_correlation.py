"""Pin id-aware pending-interrupt lookup that replaces the buggy first-wins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.streaming.interrupt_correlation import (
    PendingInterrupt,
    first_pending_interrupt,
    get_pending_interrupt_by_id,
    get_pending_interrupt_for_tool_call,
    list_pending_interrupts,
)

pytestmark = pytest.mark.unit


@dataclass
class _Interrupt:
    value: dict[str, Any]
    id: str | None = None


@dataclass
class _Task:
    interrupts: tuple[_Interrupt, ...] = ()
    id: str | None = None


@dataclass
class _State:
    tasks: tuple[_Task, ...] = ()
    interrupts: tuple[_Interrupt, ...] = ()


def _hitl(name: str, tool_call_id: str | None = None) -> dict[str, Any]:
    """Minimal LangChain HITLRequest payload for one action."""
    action: dict[str, Any] = {"name": name, "args": {}}
    if tool_call_id is not None:
        action["tool_call_id"] = tool_call_id
    return {
        "action_requests": [action],
        "review_configs": [{"action_name": name, "allowed_decisions": ["approve"]}],
    }


def test_empty_state_has_no_pending_interrupts() -> None:
    state = _State()
    assert list_pending_interrupts(state) == []
    assert first_pending_interrupt(state) is None


def test_single_pending_interrupt_in_task_is_returned() -> None:
    state = _State(
        tasks=(
            _Task(
                id="task_1",
                interrupts=(_Interrupt(value=_hitl("send_email"), id="int_1"),),
            ),
        )
    )
    pending = list_pending_interrupts(state)
    assert len(pending) == 1
    assert pending[0] == PendingInterrupt(
        interrupt_id="int_1",
        value=_hitl("send_email"),
        source_task_id="task_1",
    )


def test_pending_interrupts_returned_in_task_then_root_order() -> None:
    """Determinism matters: callers iterate in this order to render the UI."""
    state = _State(
        tasks=(
            _Task(
                id="task_a",
                interrupts=(_Interrupt(value=_hitl("a"), id="int_a"),),
            ),
            _Task(
                id="task_b",
                interrupts=(_Interrupt(value=_hitl("b"), id="int_b"),),
            ),
        ),
        interrupts=(_Interrupt(value=_hitl("c"), id="int_c"),),
    )
    pending = list_pending_interrupts(state)
    ids = [p.interrupt_id for p in pending]
    assert ids == ["int_a", "int_b", "int_c"]


def test_get_by_id_finds_the_right_interrupt_under_parallel_load() -> None:
    """Replacing first-wins: id-aware lookup MUST pick the requested one."""
    state = _State(
        tasks=(
            _Task(interrupts=(_Interrupt(value=_hitl("a"), id="int_a"),)),
            _Task(interrupts=(_Interrupt(value=_hitl("b"), id="int_b"),)),
            _Task(interrupts=(_Interrupt(value=_hitl("c"), id="int_c"),)),
        )
    )
    found = get_pending_interrupt_by_id(state, "int_b")
    assert found is not None
    assert found.value["action_requests"][0]["name"] == "b"


def test_get_by_id_returns_none_when_id_is_not_pending() -> None:
    state = _State(
        tasks=(_Task(interrupts=(_Interrupt(value=_hitl("a"), id="int_a"),)),)
    )
    assert get_pending_interrupt_by_id(state, "missing") is None


def test_get_by_tool_call_id_matches_action_request_payload() -> None:
    """HITLRequest carries ``tool_call_id`` per action; lookup uses that."""
    state = _State(
        tasks=(
            _Task(
                interrupts=(
                    _Interrupt(value=_hitl("a", tool_call_id="call_xxx"), id="int_a"),
                    _Interrupt(value=_hitl("b", tool_call_id="call_yyy"), id="int_b"),
                )
            ),
        )
    )
    found = get_pending_interrupt_for_tool_call(state, "call_yyy")
    assert found is not None
    assert found.interrupt_id == "int_b"


def test_first_pending_interrupt_matches_legacy_first_wins_behaviour() -> None:
    """Sequential-turn safety: the explicit shortcut still returns the first."""
    state = _State(
        tasks=(_Task(interrupts=(_Interrupt(value=_hitl("first"), id="int_1"),)),),
        interrupts=(_Interrupt(value=_hitl("second"), id="int_2"),),
    )
    first = first_pending_interrupt(state)
    assert first is not None
    assert first.interrupt_id == "int_1"


def test_interrupt_without_id_falls_back_to_none() -> None:
    """Snapshots from older LangGraph versions may omit ``id`` — preserve that."""
    state = _State(tasks=(_Task(interrupts=(_Interrupt(value=_hitl("a"), id=None),)),))
    pending = list_pending_interrupts(state)
    assert len(pending) == 1
    assert pending[0].interrupt_id is None


def test_non_dict_interrupt_values_are_ignored() -> None:
    """Defensive: a non-dict value should not crash the iteration."""

    class _Raw:
        value = "not a dict"

    state = _State(tasks=(_Task(interrupts=(_Raw(),)),))  # type: ignore[arg-type]
    assert list_pending_interrupts(state) == []
