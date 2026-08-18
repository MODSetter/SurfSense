"""Small utilities used by streaming orchestrators and phases."""

from __future__ import annotations

from typing import Any


def resume_step_prefix(turn_id: str) -> str:
    """Per-turn activity-id salt for resume invocations.

    Each ``stream_agent_events`` call constructs a fresh
    ``AgentEventRelayState`` with ``activity_counter=0``. Salting with
    ``turn_id`` guarantees disjoint IDs across resume streams.
    """
    return f"resume-{turn_id}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
