"""On how many days SurfSense was used: an install's stickiness, read with no ID.

A day counts when the library shows use on it: a chat turn, a document added to
the library or a Studio output from its rows, or an Agentic turn, an answer or a
plugin call from the counts file. Only whole UTC days before today are counted,
so a report sent minutes after launch reads the same as one sent at night, and
none before the first run, so history imported from the hosted app, which keeps
its own dates, is never counted as use of this install.
"""

from datetime import UTC, date, timedelta

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.chat.models import ChatMessage, MessageRole
from modules.documents.models import Document
from modules.usage_statistics.activity_counts import ActivityCounts
from modules.usage_statistics.onboarding_step import LIBRARY_TYPES


def days_used(
    session: Session,
    counts: ActivityCounts | None,
    today: date,
    days: int,
    first_run: date | None = None,
) -> int | None:
    """Of the `days` UTC days before `today`, from `first_run`'s day on, how many
    show use; None when the counts file cannot vouch for every one of them."""
    first = today - timedelta(days=days)
    if first_run is not None:
        first = max(first, first_run)
    if counts is None or not _counted_from(counts, first):
        return None
    stamped = (
        (ChatMessage.created_at, ChatMessage.role == MessageRole.USER),
        (Document.created_at, Document.document_type.in_(LIBRARY_TYPES)),
        (Artifact.created_at, true()),
    )
    used: set[date] = set()
    for column, kept in stamped:
        # Whole days: a row stamped by SQLite's CURRENT_TIMESTAMP is text with no
        # fraction, which a datetime bound would compare wrongly at midnight.
        day = func.date(column)
        used.update(
            _as_date(value)
            for value in session.scalars(
                select(day)
                .where(kept, day >= first.isoformat(), day < today.isoformat())
                .distinct()
            )
        )
    return len(used | counts.days_counted(first, today))


def _counted_from(counts: ActivityCounts, first: date) -> bool:
    """Counting starts when the API first boots on 2.2.4 or later, the launch that
    stamps the first run, so a counts file begun on `first` missed none of its days."""
    since = counts.counted_since
    return since is None or since.astimezone(UTC).date() <= first


def _as_date(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)
