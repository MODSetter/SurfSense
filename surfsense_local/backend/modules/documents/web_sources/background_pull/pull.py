"""One link read on the user's own connection into its pending note, then handed to indexing.

The row is processing while the read runs, as a file is while it is parsed, so the
plugins worker's startup sweep can fail a pull the app closed on. Logs name the
note, never the link: a session log can end up in an issue report.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from modules.documents.models import Document, DocumentStatus
from modules.documents.tasks import ingest_document
from modules.documents.web_sources.background_pull.pull_failures import (
    UNREADABLE,
    network_sentence,
    read_sentence,
)
from modules.documents.web_sources.background_pull.source_link import (
    MOVED_TO,
    SOURCE_URL,
    awaiting_pull,
)
from modules.documents.web_sources.links import routed
from modules.documents.web_sources.pullers.puller import HostCheck
from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why
from modules.egress.service import EgressDeniedError, host_destination, require
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.jobs import begin_job, finish_job, merge_metadata
from worker.notify import notify_document_updates

logger = logging.getLogger(__name__)


def pull(document_id: int) -> None:
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            document = session.get(Document, document_id)
            if document is None or not awaiting_pull(document):
                logger.info("source %s has nothing to pull", document_id)
                return
            _pull(session, document, _host_check(sessions))
    finally:
        engine.dispose()


def _host_check(sessions: sessionmaker[Session]) -> HostCheck:
    """Each host checked again, as the click asked, and stamped for Settings > Network.

    A queued pull never asks: a host turned off since the click fails it. Each
    check is its own short transaction, never one held across the read.
    """

    def reach(host: str) -> None:
        with sessions() as session:
            require(session, host_destination(f"https://{host}"), host)
            session.commit()

    return reach


def _pull(session: Session, document: Document, reach: HostCheck) -> None:
    if not begin_job(session, document):
        return
    notify_document_updates(document)
    metadata = document.document_metadata or {}
    url = metadata[SOURCE_URL]
    moved_before = MOVED_TO in metadata
    session.commit()
    try:
        pulled = routed(url).read(url, reach)
    except EgressDeniedError as error:
        _fail(session, document, network_sentence(error))
        return
    except ReadFailedError as error:
        logger.info("source %s: %s", document.id, error.why)
        if error.why is Why.MOVED:
            merge_metadata(session, document, MOVED_TO, error.host)
        _fail(session, document, read_sentence(error))
        return
    except Exception:
        # An answer the reader did not expect: never leave the row processing.
        logger.exception("source %s: the pull failed", document.id)
        session.rollback()
        _fail(session, document, UNREADABLE)
        return
    if moved_before:
        merge_metadata(session, document, MOVED_TO, None)
    merge_metadata(session, document, "fetched_at", datetime.now(UTC).isoformat())
    # Pending again, so the ingest job takes it as it takes a new note.
    if not finish_job(
        session,
        document,
        DocumentStatus.PENDING,
        title=pulled.title.strip()[:500] or url,
        content=pulled.markdown,
    ):
        return
    ingest_document(document.id)
    notify_document_updates(document)


def _fail(session: Session, document: Document, sentence: str) -> None:
    if finish_job(session, document, DocumentStatus.FAILED, error_message=sentence):
        notify_document_updates(document)
