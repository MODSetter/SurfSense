import logging
import time

import httpx
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS_BY_KEY
from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus
from modules.llm.models import ModelRole
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.resolution import (
    ModelResolutionError,
    ResolvedGeneration,
    ResolvedImageGeneration,
    resolve_generation,
    resolve_image_generation,
)
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.jobs import JobCancelledError, begin_job, finish_job, raise_if_cancelled
from worker.notify import notify_artifact_updates
from worker.studio import job_router
from worker.studio.shared import gather, persist

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500


class NoModelSelectedError(RuntimeError):
    """No model is chosen for this format's role, so the job cannot run."""


def run(artifact_id: int) -> None:
    """Take one artifact from pending to ready, or to failed with a reason."""
    # An engine per job, as ingestion does — tests repoint the DB path per case.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                logger.info("artifact %s was deleted before generation", artifact_id)
                return

            _generate(session, artifact)
    finally:
        engine.dispose()


def _generate(session: Session, artifact: Artifact) -> None:
    document = artifact.document
    started = time.monotonic()
    logger.info("studio: artifact %s format=%s starting", artifact.id, artifact.format)
    if not begin_job(session, document):
        return
    notify_artifact_updates(artifact)

    try:
        meta = artifact.artifact_metadata or {}
        sources = gather.gather(session, meta.get("source_document_ids", []))
        prompt = meta.get("prompt")
        logger.info(
            "studio: artifact %s gathered %s sources (%s chars)",
            artifact.id,
            len(sources),
            sum(len(source.content) for source in sources),
        )
        kind = job_router.Kind(artifact.format)
        fmt = FORMATS_BY_KEY[kind]
        models = [
            _choose_model(session, ModelRole(role)) for role in fmt.requires_roles
        ]
        # Options were checked at job creation; only formats that take them get them.
        extras = [meta.get("options")] if fmt.validate_options else []
        # Generation runs for minutes; the write lock must not be held across it.
        session.commit()
        raise_if_cancelled(session, document)

        # ponytail: a cancel during this call waits until the model returns.
        # Thread-kill the HTTP client if waiting the rest of the reply is too long.
        built = job_router.pipeline_for(kind)(*models, sources, prompt, *extras)
        raise_if_cancelled(session, document)

        logger.info(
            "studio: artifact %s render done in %.1fs; persisting",
            artifact.id,
            time.monotonic() - started,
        )
        persist.persist(session, artifact, document, built)

        if not finish_job(session, document, DocumentStatus.READY):
            return
        notify_artifact_updates(artifact)
        logger.info(
            "studio: artifact %s ready in %.1fs",
            artifact.id,
            time.monotonic() - started,
        )
    except JobCancelledError:
        session.rollback()
        logger.info(
            "studio: artifact %s cancelled after %.1fs",
            artifact.id,
            time.monotonic() - started,
        )
    except Exception as failure:
        session.rollback()
        document = session.get(Document, artifact.document_id)
        if document is None or document.status is DocumentStatus.CANCELLED:
            return
        if not finish_job(session, document, DocumentStatus.FAILED, _reason(failure)):
            return
        notify_artifact_updates(artifact)
        logger.exception(
            "studio: artifact %s failed after %.1fs: %s",
            artifact.id,
            time.monotonic() - started,
            document.error_message,
        )
        if isinstance(failure, NonRetryableImageError):
            return
        raise  # Huey retries; a later success clears the message.


def _reason(failure: Exception) -> str:
    """The one line the user reads in the tooltip; the traceback goes to the log."""
    if isinstance(failure, httpx.HTTPError):
        return f"The model could not be reached: {failure}"[:MESSAGE_CHARS]
    first_line = str(failure).strip().splitlines()[:1]
    return (first_line[0] if first_line else type(failure).__name__)[:MESSAGE_CHARS]


def _choose_model(
    session: Session, role: ModelRole
) -> ResolvedGeneration | ResolvedImageGeneration:
    """The model the user selected for one of the roles a format declares."""
    try:
        if role is ModelRole.IMAGE_GENERATION:
            return resolve_image_generation(session)
        return resolve_generation(session)
    except ModelResolutionError as error:
        raise NoModelSelectedError(str(error)) from error
