import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS, FORMATS_BY_KEY, Format
from modules.artifacts.models import Artifact
from modules.artifacts.schemas import FormatRead, StudioJobCreate
from modules.artifacts.script_documents.spec import document_script
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.sources import load_selected_sources
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.resolution import (
    ModelResolutionError,
    speech_selected,
)
from modules.source_scope.resolve import pruned, resolve_scope
from modules.source_scope.schemas import SourceScope
from modules.workspaces.models import Workspace
from worker.jobs import cancel_studio_job

logger = logging.getLogger(__name__)


def list_formats(session: Session) -> list[FormatRead]:
    """The catalog, each marked usable or not for the current setup."""
    formats: list[FormatRead] = []
    for fmt in FORMATS:
        available, reason = _availability(session, fmt)
        formats.append(
            FormatRead(
                key=fmt.key,
                label=fmt.label,
                requires_model_types=list(fmt.requires_model_types),
                available=available,
                unavailable_reason=reason,
            )
        )
    return formats


def create_artifact_job(
    session: Session,
    workspace: Workspace,
    payload: StudioJobCreate,
    *,
    tool_call_id: str | None = None,
) -> Artifact:
    """Validate a Studio request, create the artifact, and enqueue generation.

    The one seam both triggers share: the REST route passes no tool_call_id, a
    future create_artifact tool passes its own. Nothing else differs.
    """
    fmt = FORMATS_BY_KEY.get(payload.format)
    if fmt is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown format: {payload.format}"
        )
    available, reason = _availability(session, fmt)
    if not available:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)

    source_ids, recorded_scope = _resolve_sources(session, workspace.id, payload)
    options = _resolve_options(session, fmt, payload.options)

    document = Document(
        workspace_id=workspace.id,
        title=fmt.label,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()

    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace.id,
        format=fmt.key,
        created_by_tool_call_id=tool_call_id,
        artifact_metadata={
            "source_document_ids": source_ids,
            **recorded_scope,
            "prompt": payload.prompt,
            "options": options,
        },
    )
    session.add(artifact)
    session.flush()

    # Before enqueueing, not by the request session afterwards: the worker is
    # another process and would look for a row this request had not written.
    session.commit()
    studio_job(artifact.id)
    logger.info("studio: enqueued artifact %s format=%s", artifact.id, fmt.key)
    return artifact


def regenerate_artifact(session: Session, artifact: Artifact) -> Artifact:
    """Run a finished or failed artifact's job again: same sources and prompt,
    or the same document script.

    The artifact_metadata that created it (sources, prompt, options, spec) is still
    there, so this resets the backing document and re-enqueues — no new row.
    """
    document = artifact.document
    if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        raise HTTPException(status.HTTP_409_CONFLICT, "already generating")
    # A document script runs as stored: its format's models are never asked.
    if document_script(artifact.artifact_metadata) is None:
        available, reason = _availability(session, FORMATS_BY_KEY[artifact.format])
        if not available:
            raise HTTPException(status.HTTP_409_CONFLICT, reason)
        artifact.artifact_metadata = {
            **(artifact.artifact_metadata or {}),
            "source_document_ids": _replayed_sources(session, artifact),
        }

    document.status = DocumentStatus.PENDING
    document.error_message = None
    artifact.generation += 1
    session.commit()
    studio_job(artifact.id)
    logger.info(
        "studio: re-enqueued artifact %s generation=%s",
        artifact.id,
        artifact.generation,
    )
    return artifact


def cancel_artifact(session: Session, artifact: Artifact) -> Artifact:
    """Stop a queued or running generation. The worker exits without writing ready."""
    if not cancel_studio_job(session, artifact.document, artifact.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "nothing is running")
    return artifact


def _resolve_sources(
    session: Session, workspace_id: int, payload: StudioJobCreate
) -> tuple[list[int], dict]:
    """The job's source ids, and what the artifact records of the scope."""
    if payload.source_scope is None:
        if not payload.document_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "pick at least one source"
            )
        documents = load_selected_sources(session, workspace_id, payload.document_ids)
        return [doc.id for doc in documents], {}
    resolved = resolve_scope(session, workspace_id, payload.source_scope)
    if not resolved.ids:
        if resolved.counts.indexing:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "the chosen sources are still indexing"
            )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "pick at least one source"
        )
    scope = pruned(payload.source_scope, resolved)
    return resolved.ids, {"source_scope": scope.model_dump()}


def _replayed_sources(session: Session, artifact: Artifact) -> list[int]:
    """A recorded scope re-resolved, so files added since are used; else the
    recorded ids that still exist. Never the artifact's own document."""
    meta = artifact.artifact_metadata or {}
    if meta.get("source_scope") is not None:
        ids = resolve_scope(
            session,
            artifact.workspace_id,
            SourceScope.model_validate(meta["source_scope"]),
            exclude_document_ids=[artifact.document_id],
        ).ids
    else:
        recorded = [
            i for i in meta.get("source_document_ids", []) if i != artifact.document_id
        ]
        existing = set(
            session.scalars(
                select(Document.id).where(
                    Document.id.in_(recorded),
                    Document.workspace_id == artifact.workspace_id,
                )
            )
        )
        ids = [i for i in recorded if i in existing]
    if not ids:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "None of this artifact's sources are left."
        )
    return ids


def _resolve_options(session: Session, fmt: Format, raw: dict | None) -> dict | None:
    if fmt.validate_options is None:
        return raw
    try:
        return fmt.validate_options(session, raw)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error


# What a model type is called in a sentence, carrying its own article so the
# line reads whichever types it names. A format states the types it needs and
# this turns them into the one line the screen shows, so the wording cannot
# drift between formats that need the same thing.
_TYPE_PHRASES: dict[ModelType, str] = {
    ModelType.TEXT_GEN: "a chat model",
    ModelType.IMAGE_GEN: "an image model",
    ModelType.AUDIO_GEN: "an audio model",
}

# Sentence order, which is not the order a format lists its types in: the
# pipeline takes them in the order it runs them, and a reader wants the same
# phrasing whichever format they are looking at.
_TYPE_ORDER: tuple[ModelType, ...] = (
    ModelType.TEXT_GEN,
    ModelType.IMAGE_GEN,
    ModelType.AUDIO_GEN,
)


def _availability(session: Session, fmt: Format) -> tuple[bool, str | None]:
    """Whether this format can run, and the one line saying why not.

    Every missing type is named, not the first one noticed. A format needing
    two of them reported only whichever `requires_model_types` happened to list
    first, so selecting that one moved the reason to the other and read as the
    gate shifting rather than as half of it being met.
    """
    missing = [
        model_type
        for model_type in fmt.requires_model_types
        if session.get(SelectedModel, model_type) is None
    ]
    if missing:
        return False, _required(missing)
    if ModelType.AUDIO_GEN in fmt.requires_model_types:
        try:
            speech_selected(session)
        except ModelResolutionError:
            return False, _required([ModelType.AUDIO_GEN])
    return True, None


def _required(missing: list[ModelType]) -> str:
    """ "Needs a chat model and an image model", in a fixed reading order."""
    phrases = [_TYPE_PHRASES[kind] for kind in _TYPE_ORDER if kind in missing]
    return f"Needs {' and '.join(phrases)}"
