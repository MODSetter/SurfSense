"""The report's week: what happened since `since`, and the library as it stands now."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.chat.models import ChatMessage, ChatThread, MessageRole
from modules.documents.models import Document
from modules.usage_statistics.activity_counts import Activity, ActivityCounts
from modules.usage_statistics.buckets import (
    plugin_calls_bucket,
    sources_bucket,
    studio_outputs_bucket,
    turns_bucket,
)
from modules.usage_statistics.onboarding_step import LIBRARY_TYPES, onboarding_step
from modules.usage_statistics.schemas import WeekRead

UNKNOWN = "unknown"

_SOURCES = {
    (False, False): "none",
    (True, False): "local",
    (False, True): "remote",
    (True, True): "both",
}


def week_activity(
    session: Session,
    since: datetime,
    counts: ActivityCounts | None,
    holds_local_model: Callable[[str], bool],
) -> WeekRead:
    """What only the counts file holds is unknown for a window that began before counting did."""
    # Rows store naive UTC, as SQLite's CURRENT_TIMESTAMP writes it.
    after = since.astimezone(UTC).replace(tzinfo=None)
    counted = counts if counts is not None and counts.covers(since) else None
    return WeekRead(
        chat_turns=turns_bucket(_chat_turns(session, after)),
        agent_turns=(
            UNKNOWN
            if counted is None
            else turns_bucket(counted.total(Activity.AGENT_TURN, since))
        ),
        model_source=UNKNOWN if counted is None else _model_source(counted, since),
        sources=sources_bucket(_library_size(session)),
        studio_outputs=studio_outputs_bucket(_studio_outputs(session, after)),
        plugin_calls=(
            UNKNOWN
            if counted is None
            else plugin_calls_bucket(counted.total(Activity.PLUGIN_CALL, since))
        ),
        onboarding=onboarding_step(session, counts, holds_local_model),
    )


def _chat_turns(session: Session, after: datetime) -> int:
    """The user's turns in Basic chat; an agent thread's turns live in its engine."""
    return (
        session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .join(ChatThread, ChatThread.id == ChatMessage.chat_thread_id)
            .where(
                ChatMessage.role == MessageRole.USER,
                ChatMessage.created_at >= after,
                ChatThread.agent_engine.is_(None),
            )
        )
        or 0
    )


def _model_source(counts: ActivityCounts, since: datetime) -> str:
    local = counts.total(Activity.LOCAL_ANSWER, since) > 0
    remote = counts.total(Activity.REMOTE_ANSWER, since) > 0
    return _SOURCES[(local, remote)]


def _library_size(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.document_type.in_(LIBRARY_TYPES))
        )
        or 0
    )


def _studio_outputs(session: Session, after: datetime) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.created_at >= after)
        )
        or 0
    )
