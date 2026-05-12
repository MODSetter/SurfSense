"""Sub-agent lifecycle events the FE pairs into one timeline lane.

A sub-agent run is a high-level boundary (a whole agent invocation),
so we use the ``start`` / ``finish`` verb pair, matching how the AI SDK
spells message- and step-level lifecycles.
"""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter
from .data import format_data


def format_subagent_start(
    *,
    subagent_run_id: str,
    subagent_type: str,
    parent_tool_call_id: str,
    chat_turn_id: str | None = None,
    description: str | None = None,
    started_at: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "subagent_run_id": subagent_run_id,
        "subagent_type": subagent_type,
        "parent_tool_call_id": parent_tool_call_id,
    }
    if chat_turn_id is not None:
        payload["chat_turn_id"] = chat_turn_id
    if description is not None:
        payload["description"] = description
    if started_at is not None:
        payload["started_at"] = started_at
    return format_data("subagent-start", payload, emitter=emitter)


def format_subagent_finish(
    *,
    subagent_run_id: str,
    subagent_type: str,
    parent_tool_call_id: str,
    status: str = "completed",
    ended_at: str | None = None,
    duration_ms: int | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "subagent_run_id": subagent_run_id,
        "subagent_type": subagent_type,
        "parent_tool_call_id": parent_tool_call_id,
        "status": status,
    }
    if ended_at is not None:
        payload["ended_at"] = ended_at
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    return format_data("subagent-finish", payload, emitter=emitter)


def format_subagent_error(
    *,
    subagent_run_id: str,
    subagent_type: str,
    parent_tool_call_id: str,
    error_text: str,
    error_type: str | None = None,
    ended_at: str | None = None,
    duration_ms: int | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "subagent_run_id": subagent_run_id,
        "subagent_type": subagent_type,
        "parent_tool_call_id": parent_tool_call_id,
        "error_text": error_text,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    if ended_at is not None:
        payload["ended_at"] = ended_at
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    return format_data("subagent-error", payload, emitter=emitter)
