"""What else waits on the ingest queue, as a recording's job decides whether to
give the queue up and whether its last window is the server's last."""

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings.kind import RECORDING_MIME_PREFIX

__all__ = ["IS_RECORDING", "another_recording_queued", "other_sources_pending"]

_MIME = func.coalesce(Document.document_metadata["mime_type"].as_string(), "")
# A row that is a recording, as is_recording() tells one, for a query.
IS_RECORDING = (Document.document_type == DocumentType.FILE) & _MIME.startswith(
    RECORDING_MIME_PREFIX
)


def other_sources_pending(session: Session) -> bool:
    """A file or note that is not a recording waits: recordings never give the
    queue up to each other."""
    waiting = session.scalar(
        select(
            exists().where(
                Document.status == DocumentStatus.PENDING,
                Document.document_type.in_([DocumentType.FILE, DocumentType.NOTE]),
                or_(Document.document_type == DocumentType.NOTE, ~IS_RECORDING),
            )
        )
    )
    session.commit()  # the read took the write lock
    return bool(waiting)


def another_recording_queued(session: Session, document_id: int) -> bool:
    """Another recording will want the speech model once this one is done."""
    queued = session.scalar(
        select(
            exists().where(
                Document.id != document_id,
                Document.status.in_(
                    [DocumentStatus.PENDING, DocumentStatus.PROCESSING]
                ),
                IS_RECORDING,
            )
        )
    )
    session.commit()
    return bool(queued)
