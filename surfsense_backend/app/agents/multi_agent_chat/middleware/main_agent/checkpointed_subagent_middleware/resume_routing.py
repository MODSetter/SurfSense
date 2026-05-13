"""Route a flat ``decisions`` list to per-``tool_call_id`` resume payloads.

The frontend submits decisions in the same order the SSE stream emitted
approval cards. When multiple parallel subagents are paused, the backend uses
this module to:

1. Read ``state.interrupts`` from the parent's paused snapshot, extracting
   ``[(tool_call_id, action_count), ...]`` from each interrupt's value.
   The ``tool_call_id`` is stamped on by ``propagation.wrap_with_tool_call_id``
   inside ``task_tool``'s catch-and-stamp block when a subagent's
   ``GraphInterrupt`` bubbles up through ``[a]task``.
2. Slice the flat ``decisions`` list against that ordered pending list to
   produce the dict shape expected by ``consume_surfsense_resume``.

Both helpers are pure: callers own the state and the input decisions; we
return new structures and never mutate.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)


def slice_decisions_by_tool_call(
    decisions: list[dict[str, Any]],
    pending: Iterable[tuple[str, int]],
) -> dict[str, dict[str, Any]]:
    """Slice ``decisions`` into ``{tool_call_id: {"decisions": <slice>}}``.

    Args:
        decisions: Flat list of decisions in the order the SSE stream rendered
            them.
        pending: Ordered ``(tool_call_id, action_count)`` pairs in the same
            order. The slicer consumes ``decisions`` left-to-right.

    Returns:
        Per-``tool_call_id`` payload dict ready to be written to
        ``configurable["surfsense_resume_value"]``.

    Raises:
        ValueError: When the total expected action count differs from the
            number of decisions provided. We fail loud rather than silently
            dropping or padding so a frontend/backend contract drift surfaces
            immediately.
    """
    pending_list = list(pending)
    expected = sum(count for _, count in pending_list)
    if expected != len(decisions):
        raise ValueError(
            f"Decision count mismatch: pending tool calls expect "
            f"{expected} actions but received {len(decisions)} decisions."
        )

    routed: dict[str, dict[str, Any]] = {}
    cursor = 0
    for tool_call_id, action_count in pending_list:
        routed[tool_call_id] = {
            "decisions": decisions[cursor : cursor + action_count]
        }
        cursor += action_count
    return routed


def collect_pending_tool_calls(state: Any) -> list[tuple[str, int]]:
    """Extract ``[(tool_call_id, action_count), ...]`` from a paused parent state.

    Reads ``state.interrupts`` (the bundle langgraph aggregated from each
    paused subagent's propagated interrupt). Each interrupt value carries the
    ``tool_call_id`` that the parent's ``task`` tool was processing — see
    ``propagation.wrap_with_tool_call_id`` and ``task_tool``'s
    ``except GraphInterrupt`` chokepoint.

    Order is preserved from ``state.interrupts``, which is the order the SSE
    stream emitted approval cards. The frontend submits decisions in that
    same order, so the slicer can consume them left-to-right.

    Interrupts without a ``tool_call_id`` are skipped — they were not
    produced by our task-routing layer (e.g. parent-side HITL middleware on
    a different tool); ``stream_resume_chat`` is not responsible for routing
    those.

    Args:
        state: A langgraph ``StateSnapshot`` (or any object with an
            ``interrupts`` attribute).

    Returns:
        Ordered list of ``(tool_call_id, action_count)``. ``action_count`` is
        ``len(value["action_requests"])`` for HITL-bundle values, or ``1`` for
        scalar-style ``interrupt("...")`` values that were wrapped as
        ``{"value": ..., "tool_call_id": ...}``.

    Raises:
        ValueError: When an interrupt value carries a ``tool_call_id`` but
            the action count cannot be determined (contract bug — every
            propagated value should be either a HITL bundle or a wrapped
            scalar).
    """
    pending: list[tuple[str, int]] = []
    for idx, interrupt_obj in enumerate(getattr(state, "interrupts", ()) or ()):
        value = getattr(interrupt_obj, "value", None)
        if not isinstance(value, dict):
            logger.warning(
                "[hitl_route] interrupt[%d] skipped: value not a dict (type=%s)",
                idx,
                type(value).__name__,
            )
            continue
        tool_call_id = value.get("tool_call_id")
        if not isinstance(tool_call_id, str):
            # Should not happen post-stamping; flag loudly if a regression
            # ever lets an unstamped value reach the parent state.
            logger.warning(
                "[hitl_route] interrupt[%d] skipped: no tool_call_id stamp (keys=%s)",
                idx,
                sorted(value.keys()),
            )
            continue

        action_requests = value.get("action_requests")
        if isinstance(action_requests, list):
            pending.append((tool_call_id, len(action_requests)))
            continue
        if "value" in value:
            pending.append((tool_call_id, 1))
            continue

        raise ValueError(
            f"Interrupt for tool_call_id={tool_call_id!r} has no "
            "``action_requests`` list and is not a wrapped scalar value; "
            "cannot determine action count for resume routing."
        )

    return pending
