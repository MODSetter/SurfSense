from sqlalchemy import update
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus
from shared.queue import ingest_queue, revoke_pending, studio_queue

_ACTIVE = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class JobCancelledError(Exception):
    """The user stopped this job; the worker must exit without a Huey retry."""


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
) -> bool:
    """Write a terminal status unless cancel won the race. Returns whether we wrote."""
    result = session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.status != DocumentStatus.CANCELLED,
        )
        .values(
            status=status,
            error_message=error_message,
            content=document.content,
            title=document.title,
        )
    )
    if result.rowcount == 0:
        session.rollback()
        return False
    session.commit()
    session.refresh(document)
    return True
