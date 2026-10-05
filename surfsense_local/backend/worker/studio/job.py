import logging
import time

import httpx
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS_BY_KEY, Grounding
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.script_error import PREFIX, script_error
from modules.artifacts.script_documents.spec import (
    DocumentScript,
    document_script,
)
from modules.artifacts.script_documents.version import ArtifactVersion
from modules.artifacts.studio_documents.recipe import (
    RECIPE_KEY,
    Refinement,
    drafted,
    figure_sources,
    refinement,
    renders_as_stored,
)
from modules.documents.models import Document, DocumentStatus
from modules.llm.model_type import ModelType
from modules.llm.providers.audiocpp.memory import NotEnoughMemoryError
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.providers.openai_compatible.speech import NonRetryableSpeechError
from modules.llm.providers.protocols import TextToSpeech
from modules.llm.resolution import (
    ModelResolutionError,
    ResolvedGeneration,
    ResolvedImageGeneration,
    resolve_generation,
    resolve_image_generation,
    resolve_text_to_speech,
)
from shared import cancellation
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory, is_locked
from worker.jobs import JobCancelledError, begin_job, finish_job, raise_if_cancelled
from worker.notify import notify_artifact_updates
from worker.studio import job_router
from worker.studio.office.document import figure_shelf
from worker.studio.office.document.refine import refine
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.script_document import pipeline as script_document
from worker.studio.script_document.pipeline import ScriptRunFailedError
from worker.studio.shared import gather, persist
from worker.studio.shared.artifact import Built

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500

_DOCUMENT_OFFICE = {"docx": docx, "pdf": pdf}


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
        meta = artifact.artifact_metadata
        refining = refinement(meta)
        script = document_script(meta) if renders_as_stored(meta) else None
        if refining is not None:
            built = _refine(session, artifact, document, refining)
        elif script is not None:
            built = _run_script(session, artifact, document, script)
        else:
            built = _draft(session, artifact, document)
        raise_if_cancelled(session, document)

        logger.info(
            "studio: artifact %s render done in %.1fs; persisting",
            artifact.id,
            time.monotonic() - started,
        )
        persist.persist(session, artifact, document, built)
        if built.spec is not None:
            _keep_spec(artifact, built.spec)

        if not finish_job(
            session,
            document,
            DocumentStatus.READY,
            title=document.title,
            content=document.content,
        ):
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
        # A retry would repeat minutes of drafting and fail the same way.
        if isinstance(
            failure,
            NonRetryableImageError | NonRetryableSpeechError | NotEnoughMemoryError,
        ):
            return
        # The agent's script document is never retried: its agent reads this FAILED
        # and renders a fix as a new version, which a retry turning READY would race.
        # A Studio draft's kept spec does not count: its Retry asks the model again.
        if renders_as_stored(artifact.artifact_metadata):
            return
        # A refine is one call the user asked for; Retry asks again if they want.
        if refinement(artifact.artifact_metadata) is not None:
            return
        raise  # Huey retries; a later success clears the message.


def _draft(session: Session, artifact: Artifact, document: Document) -> Built:
    """The format's pipeline: gather the sources, ask the model, build the file."""
    meta = artifact.artifact_metadata or {}
    prompt = meta.get("prompt")
    kind = job_router.Kind(artifact.format)
    fmt = FORMATS_BY_KEY[kind]
    # The prompt is what to search for, where the format reads passages.
    query = prompt if fmt.grounding is Grounding.PASSAGES else None
    sources = gather.gather(
        session,
        meta.get("source_document_ids", []),
        query,
        focus=prompt or fmt.default_focus,
    )
    if kind in job_router.PLACES_FIGURES:
        sources = figure_shelf.with_figures(session, artifact.workspace_id, sources)
    # "Grounded on 14 of 212 sources": what reached the model, not what was ticked.
    artifact.artifact_metadata = {
        **meta,
        "grounded_document_ids": [source.document_id for source in sources],
    }
    logger.info(
        "studio: artifact %s gathered %s sources (%s chars)",
        artifact.id,
        len(sources),
        sum(len(source.content) for source in sources),
    )
    models = [
        _choose_model(session, model_type) for model_type in fmt.requires_model_types
    ]
    # Options were checked at job creation; only formats that take them get them.
    extras = [meta.get("options")] if fmt.validate_options else []
    # Generation runs for minutes; the write lock must not be held across it.
    session.commit()
    raise_if_cancelled(session, document)

    # A cancel hangs up on a model mid-reply; other stages still finish first.
    with cancellation.watching(lambda: _check_cancelled(session, document)):
        return job_router.pipeline_for(kind)(*models, sources, prompt, *extras)


def _run_script(
    session: Session, artifact: Artifact, document: Document, script: DocumentScript
) -> Built:
    """The stored script runs as it is; no model is asked and no source is gathered."""
    images = script_document.images_for(session, artifact.workspace_id, script)
    template = script_document.template_for(session, artifact.workspace_id, script)
    title = document.title
    # The script may run for two minutes; the write lock must not be held across it.
    session.commit()
    raise_if_cancelled(session, document)

    # A cancel kills the script and everything it started.
    with cancellation.watching(lambda: _check_cancelled(session, document)):
        return script_document.render(title, script, images, template)


def _refine(
    session: Session, artifact: Artifact, document: Document, refining: Refinement
) -> Built:
    """One call rewrites the base version's spec; the figures it may place are its draft's."""
    model = _choose_model(session, ModelType.TEXT_GEN)
    figures = figure_shelf.figures_of(
        session, artifact.workspace_id, figure_sources(artifact.artifact_metadata)
    )
    title = document.title
    session.commit()
    raise_if_cancelled(session, document)

    with cancellation.watching(lambda: _check_cancelled(session, document)):
        return refine(
            _DOCUMENT_OFFICE[refining.base.format], model, refining, figures, title
        )


def _keep_spec(artifact: Artifact, spec: dict) -> None:
    """A Studio draft's spec becomes v1 of its own document; a refine already has its version."""
    meta = dict(artifact.artifact_metadata or {})
    meta["spec"] = spec
    meta.setdefault(
        "version",
        ArtifactVersion(root=artifact.id, number=1, parent=None).as_metadata(),
    )
    meta.setdefault(RECIPE_KEY, drafted())
    artifact.artifact_metadata = meta


def _check_cancelled(session: Session, document: Document) -> None:
    """The check polled while a step runs; a write lock held elsewhere skips one look.

    Failing instead would kill work that had nothing wrong with it.
    """
    try:
        raise_if_cancelled(session, document)
    except OperationalError as error:
        session.rollback()
        if not is_locked(error):
            raise


def _reason(failure: Exception) -> str:
    """The line the user reads in the tooltip; the traceback goes to the log.

    A document script's traceback is the exception: the agent fixes its script from it.
    """
    if isinstance(failure, ScriptRunFailedError):
        return script_error(failure.reason(MESSAGE_CHARS - len(PREFIX)))
    if isinstance(failure, httpx.HTTPError):
        return f"The model could not be reached: {failure}"[:MESSAGE_CHARS]
    first_line = str(failure).strip().splitlines()[:1]
    return (first_line[0] if first_line else type(failure).__name__)[:MESSAGE_CHARS]


def _choose_model(
    session: Session, model_type: ModelType
) -> ResolvedGeneration | ResolvedImageGeneration | TextToSpeech:
    """The model the user selected for one of the types a format declares."""
    try:
        if model_type is ModelType.IMAGE_GEN:
            return resolve_image_generation(session)
        if model_type is ModelType.AUDIO_GEN:
            return resolve_text_to_speech(session)
        return resolve_generation(session)
    except ModelResolutionError as error:
        raise NoModelSelectedError(str(error)) from error
