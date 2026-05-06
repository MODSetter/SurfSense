"""Read the first interrupt payload from a LangGraph state snapshot."""

from __future__ import annotations

from typing import Any


def first_interrupt_value(state: Any) -> dict[str, Any] | None:
    """Return the first interrupt payload across all snapshot tasks."""

    def _extract(candidate: Any) -> dict[str, Any] | None:
        if isinstance(candidate, dict):
            value = candidate.get("value", candidate)
            return value if isinstance(value, dict) else None
        value = getattr(candidate, "value", None)
        if isinstance(value, dict):
            return value
        if isinstance(candidate, list | tuple):
            for item in candidate:
                extracted = _extract(item)
                if extracted is not None:
                    return extracted
        return None

    for task in getattr(state, "tasks", ()) or ():
        try:
            interrupts = getattr(task, "interrupts", ()) or ()
        except (AttributeError, IndexError, TypeError):
            interrupts = ()
        if not interrupts:
            extracted = _extract(task)
            if extracted is not None:
                return extracted
            continue
        for interrupt_item in interrupts:
            extracted = _extract(interrupt_item)
            if extracted is not None:
                return extracted

    try:
        state_interrupts = getattr(state, "interrupts", ()) or ()
    except (AttributeError, IndexError, TypeError):
        state_interrupts = ()
    extracted = _extract(state_interrupts)
    if extracted is not None:
        return extracted
    return None
