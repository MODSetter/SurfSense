"""Waiting for a Studio job's outcome without holding SQLite's write lock while it runs."""

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus
from shared.db import is_locked

POLL_SECONDS = 0.5
_SETTLED = (DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.CANCELLED)


@dataclass(frozen=True)
class JobOutcome:
    """Where the artifact's job stood when the wait ended."""

    status: DocumentStatus
    error_message: str | None


# The job was just queued; until a look gets through, that is where it stands.
_QUEUED = JobOutcome(status=DocumentStatus.PENDING, error_message=None)


def wait_for_outcome(
    session: Session, artifact_id: int, seconds: float
) -> JobOutcome | None:
    """The artifact's status once its job settles, or as it stands at the limit; None once deleted.

    Each look is its own short transaction: every transaction takes the write
    lock (shared.db), and the worker must write between looks.
    """
    deadline = time.monotonic() + seconds
    outcome = _QUEUED
    while True:
        try:
            row = session.execute(
                select(Document.status, Document.error_message)
                .join(Artifact, Artifact.document_id == Document.id)
                .where(Artifact.id == artifact_id)
            ).one_or_none()
            session.commit()
        except OperationalError as error:
            # Studio holds the lock while it embeds a long document, past the busy wait.
            session.rollback()
            if not is_locked(error):
                raise
        else:
            if row is None:
                return None
            outcome = JobOutcome(status=row.status, error_message=row.error_message)
        left = deadline - time.monotonic()
        if outcome.status in _SETTLED or left <= 0:
            return outcome
        time.sleep(min(POLL_SECONDS, left))
