"""Small utilities used by streaming orchestrators and phases."""

from __future__ import annotations

from typing import Any


def resume_step_prefix(turn_id: str) -> str:
    """Per-turn ``step_prefix`` for resume invocations.

    Each ``stream_agent_events`` call constructs a fresh
    ``AgentEventRelayState`` with ``thinking_step_counter=0``, so two consecutive
    resume turns would otherwise both emit ``thinking-resume-1``, ``-2`` etc.
    The frontend rehydrates ``currentThinkingSteps`` from the immediate prior
    assistant message at the start of every resume — if the new stream's IDs
    collide with the seeded ones, React renders sibling Timeline rows with the
    same key. Salting with ``turn_id`` guarantees disjoint IDs across resumes
    within one thread.
    """
    return f"thinking-resume-{turn_id}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
