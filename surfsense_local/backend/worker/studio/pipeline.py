import logging
import time

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.notify import notify_artifact_updates
from worker.studio import gather, generate, media, office, persist
from worker.studio.builders import BUILDERS

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500


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
    logger.info(
        "studio: artifact %s format=%s starting", artifact.id, artifact.format
    )
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

        # Route by family: office (model-written code), media (audio/visual), or
        # a deterministic builder.
        builder = BUILDERS.get(artifact.format)
        if artifact.format in office.OFFICE:
            family = "office"
            built = office.render(session, artifact.format, sources, prompt)
        elif artifact.format in media.MEDIA:
            family = "media"
            built = media.render(session, artifact.format, sources, prompt)
        elif builder is not None:
            family = "builder"
            raw = generate.generate(session, builder, sources, prompt)
            logger.info(
                "studio: artifact %s model reply %s chars; building",
                artifact.id,
                len(raw),
            )
            built = builder.build(raw, sources)
        else:  # pragma: no cover - the invariant test rules this out
            raise RuntimeError(f"no route for artifact format {artifact.format!r}")

        logger.info(
            "studio: artifact %s family=%s render done in %.1fs; persisting",
            artifact.id,
            family,
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
        document.error_message = f"{type(failure).__name__}: {failure}"[:MESSAGE_CHARS]
        session.commit()
        notify_artifact_updates(artifact)
        logger.info(
            "studio: artifact %s failed after %.1fs: %s",
            artifact.id,
            time.monotonic() - started,
            document.error_message,
        )
        raise  # Huey retries; a later success clears the message.
