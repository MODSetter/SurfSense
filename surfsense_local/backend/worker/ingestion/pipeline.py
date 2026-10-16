import logging

from sqlalchemy.orm import Session

from modules.documents.docling_batches import ended_in_queue as docling_batches
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings import ended_run as recording_run
from modules.documents.tasks import PRIORITY_INTERACTIVE, ingest_document
from modules.embedding.active import require_active_index
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.ingestion import chunking, indexing, parsing
from worker.ingestion.audio.failures import RecordingFailedError
from worker.ingestion.figures.word_figures_pass import queue_figures_pass_once_ready
from worker.ingestion.job_priority import queued_at
from worker.jobs import (
    JobCancelledError,
    JobYieldedError,
    begin_job,
    finish_job,
    pause_job,
    raise_if_cancelled,
)
from worker.notify import notify_document_updates

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500


def run(document_id: int, priority: int = PRIORITY_INTERACTIVE) -> None:
    """Take one document from pending to ready, or to failed with a reason.
    `priority`: the one its job was queued at."""
    # ponytail: an engine per job — tests repoint the DB path per case. Ceiling:
    # fine while jobs are seconds long and rare; pool if they get small and frequent.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            document = session.get(Document, document_id)
            if document is None:
                logger.info("document %s was deleted before ingest", document_id)
                return

            with queued_at(priority):
                _ingest(session, document)
    finally:
        engine.dispose()


def _ingest(session: Session, document: Document) -> None:
    if not begin_job(session, document):
        return
    notify_document_updates(document)

    try:
        index = require_active_index(session)
        session.commit()  # the read took the write lock; drop it before parsing
        markdown = parsing.markdown_for(document)
        raise_if_cancelled(session, document)
        passages = chunking.chunk(markdown)
        vectors = indexing.embed_passages(index, passages)
        raise_if_cancelled(session, document)
        indexing.replace_chunks(session, document, index, passages, vectors)

        # A file's text is what ingest extracted; a note's is the user's, only
        # read here, so writing it back would undo an edit made mid-ingest.
        produced = (
            {"content": markdown} if document.document_type is DocumentType.FILE else {}
        )
        if not finish_job(session, document, DocumentStatus.READY, **produced):
            return
        notify_document_updates(document)
        queue_figures_pass_once_ready(document)
    except JobCancelledError:
        session.rollback()
    except JobYieldedError as yielded:
        # A recording or a long reading gives the queue up and finishes later
        # from its checkpoint.
        session.rollback()
        if pause_job(session, document):
            ingest_document(document.id, priority=yielded.priority)
            notify_document_updates(document)
        else:
            # Cancelled as it gave the queue up: no run is left to clear its
            # work, as for one cancelled while it waited.
            recording_run.drop_when_cancelled_in_queue(document, DocumentStatus.PENDING)
            docling_batches.drop_when_cancelled_in_queue(
                document, DocumentStatus.PENDING
            )
    except Exception as failure:
        session.rollback()
        document = session.get(Document, document.id)
        if document is None or document.status is DocumentStatus.CANCELLED:
            return
        if not finish_job(
            session,
            document,
            DocumentStatus.FAILED,
            _reason(failure)[:MESSAGE_CHARS],
        ):
            return
        notify_document_updates(document)
        raise  # Huey retries; a later success clears the message.


def _reason(failure: Exception) -> str:
    # A recording's failures are sentences written for the person.
    if isinstance(failure, RecordingFailedError):
        return str(failure)
    return f"{type(failure).__name__}: {failure}"
