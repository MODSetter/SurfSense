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

from sqlalchemy.future import select

from app.db import NewChatMessage, NewChatMessageRole, shielded_async_session
from app.services.streaming.types import ActivityData, ActivityTimingData
from app.tasks.chat.persistence import persist_assistant_shell


@dataclass(frozen=True)
class ResumableActivityJournal:
    activities: list[ActivityData]
    timing: ActivityTimingData | None


async def load_resumable_activity_journal(
    chat_id: int,
) -> ResumableActivityJournal:
    """Load the paused journal rows that the resumed graph may continue."""
    async with shielded_async_session() as session:
        contents = (
            (
                await session.execute(
                    select(NewChatMessage.content)
                    .where(
                        NewChatMessage.thread_id == chat_id,
                        NewChatMessage.role == NewChatMessageRole.ASSISTANT,
                    )
                    .order_by(NewChatMessage.id.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )

    return _resumable_journal_from_messages(contents)


def _resumable_journal_from_messages(contents: Any) -> ResumableActivityJournal:
    if not isinstance(contents, (list, tuple)):
        return ResumableActivityJournal([], None)
    latest_by_id: dict[str, ActivityData] = {}
    timing: ActivityTimingData | None = None
    for content in contents:
        activities, candidate_timing = _journal_from_content(content)
        for activity in activities:
            latest_by_id.setdefault(activity["id"], activity)
        if timing is None and candidate_timing is not None:
            timing = candidate_timing
    return ResumableActivityJournal(
        activities=[
            activity
            for activity in latest_by_id.values()
            if activity["status"] == "awaiting_approval"
        ],
        timing=timing if timing and timing["status"] == "paused" else None,
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
        and (value.get("sampledAt") is None or isinstance(value["sampledAt"], str))
    )


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
