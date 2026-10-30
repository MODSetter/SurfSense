"""On how many days SurfSense was used: an install's stickiness, read with no ID.

A day counts when the library shows use on it: a chat turn, a document added to
the library or a Studio output from its rows, or an Agentic turn, an answer or a
plugin call from the counts file. Only whole UTC days before today are counted,
so a report sent minutes after launch reads the same as one sent at night.
"""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.chat.models import ChatMessage, MessageRole
from modules.documents.models import Document
from modules.usage_statistics.activity_counts import ActivityCounts
from modules.usage_statistics.onboarding_step import LIBRARY_TYPES


def days_used(
    session: Session, counts: ActivityCounts | None, today: date, days: int
) -> int | None:
    """Of the `days` UTC days before `today`, how many show use; None when the
    counts file cannot vouch for the whole window, so an Agentic day is never missed."""
    first = today - timedelta(days=days)
    since = datetime.combine(first, time(), tzinfo=UTC)
    if counts is None or not counts.covers(since):
        return None
    # Rows store naive UTC, as SQLite's CURRENT_TIMESTAMP writes it.
    start = since.replace(tzinfo=None)
    end = datetime.combine(today, time())
    stamped = (
        (ChatMessage.created_at, ChatMessage.role == MessageRole.USER),
        (Document.created_at, Document.document_type.in_(LIBRARY_TYPES)),
        (Artifact.created_at, true()),
    )
    used = {
        at.date()
        for column, kept in stamped
        for at in session.scalars(
            select(column).where(kept, column >= start, column < end)
        )
    }
    return len(used | counts.days_counted(first, today))
