"""Synthesize HITL decisions for every pending interrupt (approve-all or reject-all)."""

from __future__ import annotations

from typing import Any


def build_auto_decisions(
    state: Any, decision: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return ``(lg_resume_map, surfsense_resume_value)`` covering every pending interrupt.

    ``lg_resume_map`` is keyed by ``Interrupt.id`` for ``Command(resume=...)``;
    ``surfsense_resume_value`` is keyed by ``tool_call_id`` for the subagent
    middleware bridge. Action count is read from ``value.action_requests`` when
    present and falls back to ``1`` for wrapped scalar interrupts.
    """
    lg_resume_map: dict[str, dict[str, Any]] = {}
    routed: dict[str, dict[str, Any]] = {}

    for interrupt_obj in getattr(state, "interrupts", ()) or ():
        value = getattr(interrupt_obj, "value", None)
        if not isinstance(value, dict):
            continue
        interrupt_id = getattr(interrupt_obj, "id", None)
        if not isinstance(interrupt_id, str):
            continue

        action_requests = value.get("action_requests")
        count = len(action_requests) if isinstance(action_requests, list) else 1
        decisions = [{"type": decision} for _ in range(count)]

        lg_resume_map[interrupt_id] = {"decisions": decisions}

        tool_call_id = value.get("tool_call_id")
        if isinstance(tool_call_id, str):
            routed[tool_call_id] = {"decisions": decisions}

    return lg_resume_map, routed
