from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus
from shared.queue import ingest_queue, revoke_pending, studio_queue

_ACTIVE = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class JobCancelledError(Exception):
    """The user stopped this job; the worker must exit without a Huey retry."""


class JobYieldedError(Exception):
    """The job gave the queue to other work and will finish later, from its
    checkpoint: not a failure, and no Huey retry. It queues again at `priority`."""

    def __init__(self, priority: int) -> None:
        super().__init__(priority)
        self.priority = priority


def cancel_ingest_job(session: Session, document: Document) -> bool:
    """Revoke the ingest task. False if nothing was running."""
    if not _mark_cancelled(session, document):
        return False
    revoke_pending(ingest_queue, "ingest_document", document.id)
    return True


def cancel_studio_job(session: Session, document: Document, artifact_id: int) -> bool:
    """Revoke the studio task. False if nothing was running."""
    if not _mark_cancelled(session, document):
        return False
    revoke_pending(studio_queue, "studio_job", artifact_id)
    return True


def _mark_cancelled(session: Session, document: Document) -> bool:
    if document.status not in _ACTIVE:
        return False
    document.status = DocumentStatus.CANCELLED
    document.error_message = None
    session.commit()
    return True


def begin_job(session: Session, document: Document) -> bool:
    """Mark processing unless the row was already cancelled. False means skip."""
    result = session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.status != DocumentStatus.CANCELLED,
        )
        .values(status=DocumentStatus.PROCESSING)
    )
    session.commit()
    if result.rowcount == 0:
        return False
    session.refresh(document)
    session.commit()  # refresh takes the write lock; drop it before long work
    return True


def pause_job(session: Session, document: Document) -> bool:
    """Back to pending, so the job can queue again behind other work. False
    when a cancel won; the startup sweep leaves a pending row alone."""
    result = session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.status == DocumentStatus.PROCESSING,
        )
        .values(status=DocumentStatus.PENDING)
    )
    session.commit()
    if result.rowcount == 0:
        return False
    session.refresh(document)
    session.commit()
    return True


def merge_metadata(
    session: Session, document: Document, key: str, value: Any | None
) -> None:
    """Set one key of the row's metadata, or remove it for None. Read and
    written in one transaction, so every other key stays as last written."""
    session.commit()
    session.refresh(document, attribute_names=["document_metadata"])
    metadata = {
        name: kept
        for name, kept in (document.document_metadata or {}).items()
        if name != key
    }
    if value is not None:
        metadata[key] = value
    session.execute(
        update(Document)
        .where(Document.id == document.id)
        .values(document_metadata=metadata)
    )
    session.commit()
    session.refresh(document, attribute_names=["document_metadata"])
    session.commit()


def raise_if_cancelled(session: Session, document: Document) -> None:
    session.commit()
    session.refresh(document, attribute_names=["status"])
    cancelled = document.status is DocumentStatus.CANCELLED
    session.commit()
    if cancelled:
        raise JobCancelledError


def finish_job(
    session: Session,
    document: Document,
    status: DocumentStatus,
    error_message: str | None = None,
    **produced: str,
) -> bool:
    """Write a terminal status unless cancel won the race. Returns whether we wrote.

    Only the columns the job `produced` are written beside it, never the row as
    `begin_job` read it: a rename or a note edit committed meanwhile must stand.
    """
    result = session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.status != DocumentStatus.CANCELLED,
        )
        .values(status=status, error_message=error_message, **produced)
    )
    if result.rowcount == 0:
        session.rollback()
        return False
    session.commit()
    session.refresh(document)
    return True
