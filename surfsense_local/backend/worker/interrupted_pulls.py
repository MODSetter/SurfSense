from sqlalchemy import func, update

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.web_sources.background_pull.source_link import PULLER
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.interrupted_documents import REASON


def fail_interrupted_pulls() -> None:
    """Fail the links a previous plugins worker was pulling when the app quit.

    Called before this worker takes its first job: every pull still processing is a
    dead worker's, and Huey dropped its job. Pending ones are still queued.
    """
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            session.execute(
                update(Document)
                .where(
                    Document.status == DocumentStatus.PROCESSING,
                    Document.document_type == DocumentType.NOTE,
                    Document.content.is_(None),
                    func.json_extract(Document.document_metadata, f"$.{PULLER}").is_not(
                        None
                    ),
                )
                .values(status=DocumentStatus.FAILED, error_message=REASON)
            )
            session.commit()
    finally:
        engine.dispose()
