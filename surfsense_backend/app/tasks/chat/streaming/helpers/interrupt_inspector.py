"""Read every pending interrupt payload from a LangGraph state snapshot.

The chat-stream emit loop yields one ``data-interrupt-request`` SSE frame per
pending interrupt so parallel HITL across siblings stays addressable on the
wire (the resume slicer in ``checkpointed_subagent_middleware.resume_routing``
correlates each frame back to the right paused subagent via the stamped
``tool_call_id``). This helper produces that flat, ordered list.
"""

from __future__ import annotations

from typing import Any


def all_interrupt_entries(state: Any) -> list[tuple[dict[str, Any], str | None]]:
    """Return ``(value, interrupt_id)`` for every pending interrupt, in order.

    Walks ``state.tasks[*].interrupts`` first (langgraph's per-task buckets,
    which carry one interrupt per paused subagent) and falls back to
    ``state.interrupts`` when the per-task lists are empty. Order matches the
    snapshot's iteration order so the emit-time order on the SSE stream agrees
    with the resume slicer's consumption order.

    The ``interrupt_id`` (langgraph ``Interrupt.id``) is the only stable handle
    for parent-side interrupts (doom-loop, permission asks) that carry no
    ``tool_call_id``; it lets the frontend render and resume them.

    Defensive against malformed snapshots: tasks/interrupts that raise on
    attribute access are skipped silently. Non-dict values are skipped — the
    chat-stream contract requires structured interrupt payloads.
    """

    def _extract(candidate: Any) -> tuple[dict[str, Any], str | None] | None:
        if isinstance(candidate, dict):
            value = candidate.get("value", candidate)
            interrupt_id = candidate.get("id")
        else:
            value = getattr(candidate, "value", None)
            interrupt_id = getattr(candidate, "id", None)
        if not isinstance(value, dict):
            return None
        return value, (str(interrupt_id) if interrupt_id is not None else None)

    entries: list[tuple[dict[str, Any], str | None]] = []
    saw_task_interrupt = False

    for task in getattr(state, "tasks", ()) or ():
        try:
            interrupts = getattr(task, "interrupts", ()) or ()
        except (AttributeError, IndexError, TypeError):
            interrupts = ()
        if interrupts:
            saw_task_interrupt = True
            for interrupt_item in interrupts:
                extracted = _extract(interrupt_item)
                if extracted is not None:
                    entries.append(extracted)

    if saw_task_interrupt:
        return entries

    try:
        state_interrupts = getattr(state, "interrupts", ()) or ()
    except (AttributeError, IndexError, TypeError):
        state_interrupts = ()
    for interrupt_item in state_interrupts:
        extracted = _extract(interrupt_item)
        if extracted is not None:
            entries.append(extracted)
    return entries


def all_interrupt_values(state: Any) -> list[dict[str, Any]]:
    """Interrupt payloads across the snapshot, in traversal order (ids dropped)."""
    return [value for value, _ in all_interrupt_entries(state)]
