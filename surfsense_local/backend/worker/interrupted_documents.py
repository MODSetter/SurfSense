from collections.abc import Collection

from sqlalchemy import update

from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory

REASON = "interrupted when the app closed"


def fail_interrupted_documents(kinds: Collection[DocumentType]) -> None:
    """Fail the documents a previous worker left processing when the app quit.

    Called before this worker takes its first job, so every processing document
    of its kinds is a dead worker's, and Huey has already dropped that job.
    Pending ones are still queued and are left for this worker.
    """
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            session.execute(
                update(Document)
                .where(
                    Document.status == DocumentStatus.PROCESSING,
                    Document.document_type.in_(list(kinds)),
                )
                .values(status=DocumentStatus.FAILED, error_message=REASON)
            )
            session.commit()
    finally:
        engine.dispose()
