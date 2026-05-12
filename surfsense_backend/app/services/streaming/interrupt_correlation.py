"""Id-aware lookup of pending LangGraph interrupts (replaces first-wins)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PendingInterrupt:
    interrupt_id: str | None
    value: dict[str, Any]
    source_task_id: str | None = None


def list_pending_interrupts(state: Any) -> list[PendingInterrupt]:
    out: list[PendingInterrupt] = []

    for task in getattr(state, "tasks", None) or ():
        task_id = _safe_str(getattr(task, "id", None))
        for it in getattr(task, "interrupts", None) or ():
            value = _coerce_interrupt_value(it)
            if value is None:
                continue
            interrupt_id = _safe_str(getattr(it, "id", None))
            out.append(
                PendingInterrupt(
                    interrupt_id=interrupt_id,
                    value=value,
                    source_task_id=task_id,
                )
            )

    for it in getattr(state, "interrupts", None) or ():
        value = _coerce_interrupt_value(it)
        if value is None:
            continue
        interrupt_id = _safe_str(getattr(it, "id", None))
        out.append(PendingInterrupt(interrupt_id=interrupt_id, value=value))

    return out


def get_pending_interrupt_by_id(
    state: Any, interrupt_id: str
) -> PendingInterrupt | None:
    for pending in list_pending_interrupts(state):
        if pending.interrupt_id == interrupt_id:
            return pending
    return None


def get_pending_interrupt_for_tool_call(
    state: Any, tool_call_id: str
) -> PendingInterrupt | None:
    for pending in list_pending_interrupts(state):
        actions = pending.value.get("action_requests")
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("tool_call_id") == tool_call_id:
                return pending
    return None


def first_pending_interrupt(state: Any) -> PendingInterrupt | None:
    """Explicit opt-in to legacy first-wins; prefer the id-aware helpers above."""
    pending = list_pending_interrupts(state)
    return pending[0] if pending else None


def _coerce_interrupt_value(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item if item else None
    value = getattr(item, "value", None)
    if isinstance(value, dict):
        return value if value else None
    return None


def _safe_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
