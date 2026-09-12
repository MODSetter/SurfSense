import logging

from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.ingestion import chunking, embedding, indexing, parsing
from worker.notify import notify_document_updates

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500


def run(document_id: int) -> None:
    """Take one document from pending to ready, or to failed with a reason."""
    # ponytail: an engine per job — tests repoint the DB path per case. Ceiling:
    # fine while jobs are seconds long and rare; pool if they get small and frequent.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            document = session.get(Document, document_id)
            if document is None:
                logger.info("document %s was deleted before ingest", document_id)
                return

            _ingest(session, document)
    finally:
        engine.dispose()


def _ingest(session: Session, document: Document) -> None:
    document.status = DocumentStatus.PROCESSING
    session.commit()
    notify_document_updates(document)

    try:
        markdown = parsing.markdown_for(document)
        passages = chunking.chunk(markdown)
        texts = [passage.text for passage in passages]
        vectors = embedding.embed(texts) if texts else []
        indexing.replace_chunks(session, document, passages, vectors)

        document.content = markdown
        document.status = DocumentStatus.READY
        document.error_message = None
        session.commit()
        notify_document_updates(document)
    except Exception as failure:
        session.rollback()
        document.status = DocumentStatus.FAILED
        document.error_message = f"{type(failure).__name__}: {failure}"[:MESSAGE_CHARS]
        session.commit()
        notify_document_updates(document)
        raise  # Huey retries; a later success clears the message.
