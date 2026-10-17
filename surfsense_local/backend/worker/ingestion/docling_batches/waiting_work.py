"""What a long Docling reading gives the queue up to: a file or note whose ingest
waits at the reading's own priority or above, so a bulk copy started after it
does not finish first. Not a recording, as for a recording's job, and not
another reading that gave the queue up itself, or long readings would take turns
until all ended together."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from modules.documents.docling_batches.layout import batches_dir
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings
from worker.ingestion.audio.waiting_work import IS_RECORDING
from worker.ingestion.queued_ingests import ingests_queued_from

__all__ = ["sources_to_give_way_to"]


def sources_to_give_way_to(session: Session, priority: int) -> bool:
    queued = ingests_queued_from(priority)
    if not queued:
        return False  # a pending row with no job queued is waited on by nobody
    waiting = session.execute(
        select(Document.workspace_id, Document.id).where(
            Document.status == DocumentStatus.PENDING,
            Document.document_type.in_([DocumentType.FILE, DocumentType.NOTE]),
            or_(Document.document_type == DocumentType.NOTE, ~IS_RECORDING),
        )
    ).all()
    session.commit()  # the read took the write lock
    storage = get_storage_settings()
    # Matched here, not in SQL: a bulk copy queues more ids than SQLite binds.
    return any(
        document_id in queued
        and not batches_dir(storage.document_dir(workspace_id, document_id)).is_dir()
        for workspace_id, document_id in waiting
    )
