"""One link pulled through its plugin into its pending note, then handed to indexing.

The row is processing while the plugin works, as a file is while it is read, so the
plugins worker's startup sweep can fail a pull the app closed on.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus
from modules.documents.tasks import ingest_document
from modules.documents.web_sources.background_pull.pull_failures import (
    UNREACHABLE,
    UNREADABLE,
    license_sentence,
    network_sentence,
)
from modules.documents.web_sources.background_pull.source_link import (
    PULLER,
    SOURCE_URL,
    awaiting_pull,
)
from modules.documents.web_sources.links import puller_named
from modules.documents.web_sources.plugin_calls.plugin_access import (
    LicenseRefusedError,
    PluginAccess,
    plugin_access,
)
from modules.documents.web_sources.plugin_calls.plugin_call import (
    PluginUnavailableError,
    ToolRefusedError,
    call_plugin,
)
from modules.documents.web_sources.pullers.puller import Results, ToolCall
from modules.egress.service import EgressDeniedError
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.jobs import begin_job, finish_job, merge_metadata
from worker.notify import notify_document_updates

logger = logging.getLogger(__name__)

# Per tool call: a video's comments or a place's reviews may take minutes to read.
READ_SECONDS = 600


def pull(document_id: int) -> None:
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            document = session.get(Document, document_id)
            if document is None or not awaiting_pull(document):
                logger.info("source %s has nothing to pull", document_id)
                return
            _pull(session, document)
    finally:
        engine.dispose()


def _pull(session: Session, document: Document) -> None:
    if not begin_job(session, document):
        return
    notify_document_updates(document)
    metadata = document.document_metadata or {}
    puller = puller_named(metadata[PULLER])
    url = metadata[SOURCE_URL]
    try:
        access = plugin_access(session, puller.plugin_id)
        session.commit()
        pulled = puller.written(url, asyncio.run(_answers(access, puller.calls(url))))
    except LicenseRefusedError as error:
        _fail(session, document, license_sentence(error))
        return
    except EgressDeniedError as error:
        session.rollback()
        _fail(session, document, network_sentence(error))
        return
    except PluginUnavailableError as error:
        logger.warning("source %s: %s", document.id, error)
        _fail(session, document, UNREACHABLE)
        return
    except ToolRefusedError as error:
        logger.info("source %s: %s", document.id, error)
        _fail(session, document, UNREADABLE)
        return
    except Exception:
        # A plugin answer a puller cannot read: never leave the row processing.
        logger.exception("source %s: the pull failed", document.id)
        session.rollback()
        _fail(session, document, UNREADABLE)
        return
    if pulled is None:
        _fail(session, document, UNREADABLE)
        return
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


async def _answers(access: PluginAccess, calls: list[ToolCall]) -> Results:
    """Every call at once; an optional one that fails leaves its tool with no items."""
    answered = await asyncio.gather(
        *(call_plugin(access, c.tool, c.arguments, READ_SECONDS) for c in calls),
        return_exceptions=True,
    )
    results: Results = {}
    for call, answer in zip(calls, answered, strict=True):
        if isinstance(answer, BaseException):
            if not call.optional or isinstance(answer, LicenseRefusedError):
                raise answer
            logger.info("optional %s failed: %s", call.tool, answer)
            answer = []
        results[call.tool] = answer
    return results


def _fail(session: Session, document: Document, sentence: str) -> None:
    if finish_job(session, document, DocumentStatus.FAILED, error_message=sentence):
        notify_document_updates(document)
