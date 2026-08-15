"""Pre-write a fresh assistant row for this resume turn.

The original (interrupted) ``stream_new_chat`` invocation already persisted
its own assistant row anchored to a different ``turn_id``; resume allocates a
new ``turn_id`` (per-request, see ``orchestrator``) so we need a separate row
keyed on the same ``(thread_id, turn_id, ASSISTANT)`` invariant.

Idempotent against migration 141's partial unique index — recovers the
existing id on retry.

Resume does NOT emit ``data-user-message-id``: the user row is from the
original interrupted turn (different ``turn_id``) and is never re-persisted
here. See B5 in the ``sse-based_message_id_handshake`` plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.db import shielded_async_session
from app.services.streaming.types import ActivityData, ActivityTimingData
from app.tasks.chat.persistence import (
    load_assistant_message_for_turn,
    persist_assistant_shell,
)


@dataclass(frozen=True)
class ResumableActivityJournal:
    activities: list[ActivityData]
    timing: ActivityTimingData | None
    activity_id_by_tool_call: dict[str, str]
    tool_call_ids: list[str]


def order_resume_tool_call_ids(
    journal: ResumableActivityJournal,
    pending_tool_call_ids: list[str],
) -> list[str]:
    """Prefer checkpoint interrupt order, then persisted activity sequence."""
    preferred_by_activity = {
        journal.activity_id_by_tool_call[tool_call_id]: tool_call_id
        for tool_call_id in journal.tool_call_ids
        if tool_call_id in journal.activity_id_by_tool_call
    }
    ordered: list[str] = []
    for pending_id in pending_tool_call_ids:
        activity_id = journal.activity_id_by_tool_call.get(pending_id)
        preferred_id = preferred_by_activity.get(activity_id) if activity_id else None
        if preferred_id and preferred_id not in ordered:
            ordered.append(preferred_id)
    ordered.extend(
        tool_call_id
        for tool_call_id in journal.tool_call_ids
        if tool_call_id not in ordered
    )
    return ordered


async def load_resumable_activity_journal(
    chat_id: int,
    *,
    turn_id: str | None,
) -> ResumableActivityJournal:
    """Load the exact paused assistant row the resumed graph may continue."""
    async with shielded_async_session() as session:
        message = await load_assistant_message_for_turn(
            session,
            chat_id=chat_id,
            turn_id=turn_id,
        )
    return _resumable_journal_from_content(message.content if message else None)


def _resumable_journal_from_content(content: Any) -> ResumableActivityJournal:
    activities, timing = _journal_from_content(content)
    awaiting_activities = sorted(
        (
            activity
            for activity in activities
            if activity["status"] == "awaiting_approval"
        ),
        key=lambda activity: (activity["sequence"], activity["id"]),
    )
    awaiting = {activity["id"]: activity for activity in awaiting_activities}
    bindings, preferred_ids = _activity_bindings_from_content(
        content, valid_activity_ids=awaiting.keys()
    )
    return ResumableActivityJournal(
        activities=awaiting_activities,
        timing=timing if timing and timing["status"] == "paused" else None,
        activity_id_by_tool_call=bindings,
        tool_call_ids=[
            preferred_ids[activity["id"]]
            for activity in awaiting_activities
            if activity["id"] in preferred_ids
        ],
    )


def _journal_from_content(
    content: Any,
) -> tuple[list[ActivityData], ActivityTimingData | None]:
    if not isinstance(content, list):
        return [], None
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "data-activities":
            continue
        data = part.get("data")
        activities = data.get("activities") if isinstance(data, dict) else None
        if not isinstance(activities, list):
            return [], None
        timing = data.get("timing")
        return (
            [
                cast(ActivityData, activity)
                for activity in activities
                if _is_activity(activity)
            ],
            cast(ActivityTimingData, timing) if _is_activity_timing(timing) else None,
        )
    return [], None


def _is_activity(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status")
        in {
            "running",
            "awaiting_approval",
            "completed",
            "error",
            "cancelled",
            "interrupted",
        }
        and isinstance(value.get("id"), str)
        and isinstance(value.get("sequence"), int)
        and isinstance(value.get("kind"), str)
        and isinstance(value.get("title"), str)
        and isinstance(value.get("category"), str)
        and isinstance(value.get("iconKey"), str)
        and isinstance(value.get("startedAt"), str)
    )


def _is_activity_timing(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") in {"running", "paused", "completed"}
        and isinstance(value.get("activeDurationMs"), int)
        and value["activeDurationMs"] >= 0
    )


def _activity_bindings_from_content(
    content: Any,
    *,
    valid_activity_ids: Any,
) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(content, list):
        return {}, {}
    valid_ids = set(valid_activity_ids)
    bindings: dict[str, str] = {}
    preferred_id_by_activity: dict[str, str] = {}
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "tool-call":
            continue
        metadata = part.get("metadata")
        activity_id = metadata.get("activityId") if isinstance(metadata, dict) else None
        if not isinstance(activity_id, str) or activity_id not in valid_ids:
            continue
        preferred_id: str | None = None
        for key in ("langchainToolCallId", "toolCallId"):
            tool_call_id = part.get(key)
            if isinstance(tool_call_id, str) and tool_call_id:
                bindings[tool_call_id] = activity_id
                if preferred_id is None:
                    preferred_id = tool_call_id
        if preferred_id is not None:
            preferred_id_by_activity.setdefault(activity_id, preferred_id)
    return bindings, preferred_id_by_activity


async def persist_resume_assistant_shell(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
) -> int | None:
    return await persist_assistant_shell(
        chat_id=chat_id,
        user_id=user_id,
        turn_id=turn_id,
    )
