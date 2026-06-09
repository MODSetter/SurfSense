import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.db import Document, DocumentStatus

logger = logging.getLogger(__name__)


async def rollback_and_persist_failure(
    session: AsyncSession, document: Document, message: str
) -> None:
    """Roll back the current transaction and best-effort persist a failed status.

    Called exclusively from except blocks — must never raise, or the new exception
    would chain with the original and mask it entirely.
    """
    try:
        await session.rollback()
    except Exception:
        # Session is completely dead; surface it but never raise.
        logger.warning(
            "Rollback failed; cannot persist failed status for document %s",
            getattr(document, "id", "unknown"),
            exc_info=True,
        )
        return
    try:
        await session.refresh(document)
        document.updated_at = datetime.now(UTC)
        document.status = DocumentStatus.failed(message)
        await session.commit()
    except Exception:
        # Best-effort: the document stays non-ready and is retried next sync.
        # Log it so a permanently-stuck document is at least traceable.
        logger.warning(
            "Could not persist failed status for document %s; will retry next sync",
            getattr(document, "id", "unknown"),
            exc_info=True,
        )
        with contextlib.suppress(Exception):
            await session.rollback()


def attach_chunks_to_document(document: Document, chunks: list) -> None:
    """Assign chunks to a document without triggering SQLAlchemy async lazy loading."""
    set_committed_value(document, "chunks", chunks)
    session = object_session(document)
    if session is not None:
        if document.id is not None:
            for chunk in chunks:
                chunk.document_id = document.id
        session.add_all(chunks)
