import logging
import time

import httpx
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS_BY_KEY
from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus
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
    document.status = DocumentStatus.PROCESSING
    session.commit()
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
        models = [
            _choose_model(session, ModelRole(role))
            for role in FORMATS_BY_KEY[kind].requires_roles
        ]
        # Generation runs for minutes; a transaction held across it fails on the
        # first write after (SQLITE_BUSY_SNAPSHOT) as soon as the API writes.
        session.commit()

        built = job_router.pipeline_for(kind)(*models, sources, prompt)

        logger.info(
            "studio: artifact %s render done in %.1fs; persisting",
            artifact.id,
            time.monotonic() - started,
        )
        persist.persist(session, artifact, document, built)

        document.status = DocumentStatus.READY
        document.error_message = None
        session.commit()
        notify_artifact_updates(artifact)
        logger.info(
            "studio: artifact %s ready in %.1fs",
            artifact.id,
            time.monotonic() - started,
        )
    except Exception as failure:
        session.rollback()
        document.status = DocumentStatus.FAILED
        document.error_message = _reason(failure)
        session.commit()
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
