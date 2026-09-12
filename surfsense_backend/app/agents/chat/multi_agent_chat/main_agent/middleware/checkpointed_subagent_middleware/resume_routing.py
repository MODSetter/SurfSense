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
3. Re-key those slices by ``Interrupt.id`` (langgraph's primitive) for use as
   the parent-level ``Command(resume={interrupt_id: payload})`` input — the
   only shape langgraph accepts when multiple interrupts are pending.

All helpers are pure: callers own the state and the input decisions; we
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

    Routes by identity when every decision carries a ``tool_call_id``, else by
    position in ``pending`` order. Raises on any count or id mismatch.
    """
    pending_list = list(pending)
    if decisions and all(d.get("tool_call_id") for d in decisions):
        return _route_by_id(decisions, pending_list)

    expected = sum(count for _, count in pending_list)
    if expected != len(decisions):
        raise ValueError(
            f"Decision count mismatch: pending tool calls expect "
            f"{expected} actions but received {len(decisions)} decisions."
        )

    routed: dict[str, dict[str, Any]] = {}
    cursor = 0
    for tool_call_id, action_count in pending_list:
        routed[tool_call_id] = {"decisions": decisions[cursor : cursor + action_count]}
        cursor += action_count
    return routed


def _route_by_id(
    decisions: list[dict[str, Any]],
    pending_list: list[tuple[str, int]],
) -> dict[str, dict[str, Any]]:
    """Route id-stamped decisions to their pending tool call, validating identity."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        grouped.setdefault(str(decision["tool_call_id"]), []).append(decision)

    pending_ids = {tool_call_id for tool_call_id, _ in pending_list}
    if set(grouped) != pending_ids:
        raise ValueError(
            "Decision routing mismatch: decisions target "
            f"{sorted(grouped)} but pending tool calls are {sorted(pending_ids)}."
        )

    routed: dict[str, dict[str, Any]] = {}
    for tool_call_id, action_count in pending_list:
        slice_ = grouped[tool_call_id]
        if len(slice_) != action_count:
            raise ValueError(
                f"Decision count mismatch for tool_call_id={tool_call_id!r}: "
                f"expected {action_count} action(s) but received {len(slice_)}."
            )
        routed[tool_call_id] = {"decisions": slice_}
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
        if value.get("type") == "structured_question":
            pending.append((tool_call_id, 1))
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


def collect_pending_parent_interrupts(state: Any) -> list[tuple[str, int]]:
    """Ordered ``(interrupt_id, action_count)`` for unstamped parent-graph interrupts.

    Complements :func:`collect_pending_tool_calls`: main-agent
    ``PermissionMiddleware`` asks and ``DoomLoopMiddleware`` pauses carry no
    ``tool_call_id`` (they never cross a ``task`` call), so they must be routed
    by ``Interrupt.id`` instead. ``action_count`` defaults to 1 for scalar
    payloads (e.g. doom-loop) with no ``action_requests``.
    """
    pending: list[tuple[str, int]] = []
    for interrupt_obj in getattr(state, "interrupts", ()) or ():
        value = getattr(interrupt_obj, "value", None)
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("tool_call_id"), str):
            continue  # subagent-routed; owned by collect_pending_tool_calls
        interrupt_id = getattr(interrupt_obj, "id", None)
        if not isinstance(interrupt_id, str):
            continue
        action_requests = value.get("action_requests")
        count = (
            len(action_requests)
            if isinstance(action_requests, list) and action_requests
            else 1
        )
        pending.append((interrupt_id, count))
    return pending


def build_parent_resume_map(
    decisions: list[dict[str, Any]],
    parent_pending: list[tuple[str, int]],
) -> dict[str, Any]:
    """Map ``Interrupt.id → resume_value`` for parent-side interrupts.

    Single-action asks deliver the raw decision dict (the site's
    ``interrupt()`` return); parent sites read it directly and never unwrap a
    ``{"decisions": [...]}`` bundle. Raises on a decision-count mismatch.
    """
    expected = sum(count for _, count in parent_pending)
    if expected != len(decisions):
        raise ValueError(
            f"Decision count mismatch: parent-side interrupts expect "
            f"{expected} actions but received {len(decisions)} decisions."
        )

    out: dict[str, Any] = {}
    cursor = 0
    for interrupt_id, count in parent_pending:
        chunk = decisions[cursor : cursor + count]
        cursor += count
        out[interrupt_id] = chunk[0] if count == 1 else {"decisions": chunk}
    return out


def build_lg_resume_map(
    state: Any, by_tool_call_id: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Map ``Interrupt.id → resume_payload`` for langgraph's multi-interrupt resume.

    ``stream_resume_chat`` builds ``by_tool_call_id`` via
    :func:`slice_decisions_by_tool_call`. Langgraph's ``Command(resume=...)``
    requires ``Interrupt.id`` keys (not our ``tool_call_id`` stamps) when the
    parent state has multiple pending interrupts. This pure helper re-keys the
    slice without mutating it, and skips entries that can't be paired (no
    stamp, no slice) so contract drift surfaces as a count mismatch at the
    call site instead of a silent mis-route.

    The two key spaces serve two different consumers:
    - ``surfsense_resume_value`` (keyed by ``tool_call_id``): read by the
      subagent bridge inside ``task_tool``.
    - ``Command(resume=...)`` (keyed by ``Interrupt.id``): read by langgraph's
      pregel to wake each pending interrupt site.

    Args:
        state: A langgraph ``StateSnapshot`` (or any object with an
            ``interrupts`` iterable).
        by_tool_call_id: Output of :func:`slice_decisions_by_tool_call`.

    Returns:
        Dict ready to be passed as ``Command(resume=<this>)``.
    """
    out: dict[str, dict[str, Any]] = {}
    for interrupt_obj in getattr(state, "interrupts", ()) or ():
        value = getattr(interrupt_obj, "value", None)
        if not isinstance(value, dict):
            continue
        tool_call_id = value.get("tool_call_id")
        if not isinstance(tool_call_id, str):
            continue
        interrupt_id = getattr(interrupt_obj, "id", None)
        if not isinstance(interrupt_id, str):
            continue
        payload = by_tool_call_id.get(tool_call_id)
        if payload is None:
            continue
        out[interrupt_id] = payload
    return out
