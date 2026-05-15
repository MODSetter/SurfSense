"""Read every pending interrupt payload from a LangGraph state snapshot.

The chat-stream emit loop yields one ``data-interrupt-request`` SSE frame per
pending interrupt so parallel HITL across siblings stays addressable on the
wire (the resume slicer in ``checkpointed_subagent_middleware.resume_routing``
correlates each frame back to the right paused subagent via the stamped
``tool_call_id``). This helper produces that flat, ordered list.
"""

from __future__ import annotations

from typing import Any


def all_interrupt_values(state: Any) -> list[dict[str, Any]]:
    """Return every interrupt payload across the snapshot, in traversal order.

    Walks ``state.tasks[*].interrupts`` first (langgraph's per-task buckets,
    which carry one interrupt per paused subagent) and falls back to
    ``state.interrupts`` when the per-task lists are empty. Order matches the
    snapshot's iteration order so the emit-time order on the SSE stream agrees
    with ``collect_pending_tool_calls`` consumption order on resume.

    Defensive against malformed snapshots: tasks/interrupts that raise on
    attribute access are skipped silently. Non-dict values are skipped — the
    chat-stream contract requires structured interrupt payloads.
    """

    def _extract(candidate: Any) -> dict[str, Any] | None:
        if isinstance(candidate, dict):
            value = candidate.get("value", candidate)
            return value if isinstance(value, dict) else None
        value = getattr(candidate, "value", None)
        if isinstance(value, dict):
            return value
        return None

    values: list[dict[str, Any]] = []
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
                    values.append(extracted)

    if saw_task_interrupt:
        return values

    try:
        state_interrupts = getattr(state, "interrupts", ()) or ()
    except (AttributeError, IndexError, TypeError):
        state_interrupts = ()
    for interrupt_item in state_interrupts:
        extracted = _extract(interrupt_item)
        if extracted is not None:
            values.append(extracted)
    return values
