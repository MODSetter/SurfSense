import logging

from modules.documents.docling_batches import ended_in_queue as docling_batches
from modules.documents.models import Document, DocumentStatus
from modules.documents.recordings import ended_run as recording_run
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.jobs import finish_job
from worker.notify import notify_document_updates

logger = logging.getLogger(__name__)

# As the pipeline cuts a failure's reason.
MESSAGE_CHARS = 500


def fail_unloadable_ingest(document_id: int, unloadable: ImportError) -> None:
    """Fail a source whose ingest code would not load, with the reason.

    Outside `worker.ingestion`, the package that failed to import. One line, not
    a traceback: a folder's every file fails alike, and a traceback each would
    push the rest of the session log out of an issue report.
    """
    reason = f"{type(unloadable).__name__}: {unloadable}"[:MESSAGE_CHARS]
    logger.error(
        "document %s cannot be ingested: %s (%s)",
        document_id,
        reason,
        unloadable.path or unloadable.name,
    )
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            document = session.get(Document, document_id)
            if document is None:
                return
            was = document.status
            if not finish_job(session, document, DocumentStatus.FAILED, reason):
                return
            # finish_job's refresh took the write lock; not across an HTTP call.
            session.commit()
            # A recording or a long reading that gave the queue up kept its work
            # for a run that will not come, as one cancelled in the queue does.
            recording_run.drop_when_cancelled_in_queue(document, was)
            docling_batches.drop_when_cancelled_in_queue(document, was)
            notify_document_updates(document)
    finally:
        engine.dispose()
