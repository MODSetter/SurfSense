"""Resume-payload shaping and pending-interrupt detection for subagents.

Splits the work of "given a state snapshot and a parent-stashed resume value,
produce the right ``Command(resume=...)`` for the subagent" into pure helpers.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import Command


def hitlrequest_action_count(pending_value: Any) -> int:
    """Bundle size for a LangChain ``HITLRequest`` payload; ``0`` for non-bundle interrupts."""
    if not isinstance(pending_value, dict):
        return 0
    actions = pending_value.get("action_requests")
    if isinstance(actions, list):
        return len(actions)
    return 0


def fan_out_decisions_to_match(resume_value: Any, expected_count: int) -> Any:
    """Pad a single-decision resume to N entries so an ``action_requests=N`` bundle accepts it."""
    if expected_count <= 1:
        return resume_value
    if not isinstance(resume_value, dict):
        return resume_value
    decisions = resume_value.get("decisions")
    if not isinstance(decisions, list) or len(decisions) >= expected_count:
        return resume_value
    if not decisions:
        return resume_value
    padded = list(decisions) + [decisions[-1]] * (expected_count - len(decisions))
    return {**resume_value, "decisions": padded}


def get_first_pending_subagent_interrupt(state: Any) -> tuple[str | None, Any]:
    """First pending ``(interrupt_id, value)``; ``(None, None)`` if no interrupt.

    Assumes at most one pending interrupt per snapshot (sequential tool nodes).
    Parallel tool nodes would need an id-aware lookup instead of first-wins.
    """
    if state is None:
        return None, None
    for it in getattr(state, "interrupts", None) or ():
        value = getattr(it, "value", None)
        interrupt_id = getattr(it, "id", None)
        if value is not None:
            return (
                interrupt_id if isinstance(interrupt_id, str) else None,
                value,
            )
    for sub_task in getattr(state, "tasks", None) or ():
        for it in getattr(sub_task, "interrupts", None) or ():
            value = getattr(it, "value", None)
            interrupt_id = getattr(it, "id", None)
            if value is not None:
                return (
                    interrupt_id if isinstance(interrupt_id, str) else None,
                    value,
                )
    return None, None


def build_resume_command(resume_value: Any, pending_id: str | None) -> Command:
    """``Command(resume={id: value})`` when ``id`` is known, else fall back to scalar."""
    if pending_id is None:
        return Command(resume=resume_value)
    return Command(resume={pending_id: resume_value})
