import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS, FORMATS_BY_KEY, Format
from modules.artifacts.models import Artifact
from modules.artifacts.schemas import FormatRead, StudioJobCreate
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.sources import load_selected_sources
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.resolution import ModelResolutionError, resolve_text_to_speech
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
                requires_roles=list(fmt.requires_roles),
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

    documents = _resolve_sources(session, workspace.id, payload.document_ids)
    options = _resolve_options(fmt, payload.options)

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
            "source_document_ids": [doc.id for doc in documents],
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
    """Run a finished or failed artifact's job again: same sources and prompt.

    The artifact_metadata that created it (sources, prompt, options) is still
    there, so this resets the backing document and re-enqueues — no new row.
    """
    document = artifact.document
    if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        raise HTTPException(status.HTTP_409_CONFLICT, "already generating")
    available, reason = _availability(session, FORMATS_BY_KEY[artifact.format])
    if not available:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)

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
    session: Session, workspace_id: int, document_ids: list[int]
) -> list[Document]:
    if not document_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "pick at least one source"
        )
    return load_selected_sources(session, workspace_id, document_ids)


def _resolve_options(fmt: Format, raw: dict | None) -> dict | None:
    if fmt.validate_options is None:
        return raw
    try:
        return fmt.validate_options(raw)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error


# What a role is called in a sentence, carrying its own article so the line
# reads whichever roles it names. A format states the roles it needs and this
# turns them into the one line the screen shows, so the wording cannot drift
# between formats that need the same thing.
_ROLE_PHRASES: dict[ModelRole, str] = {
    ModelRole.GENERATION: "a chat model",
    ModelRole.IMAGE_GENERATION: "an image model",
}

# Sentence order, which is not the order a format lists its roles in: the
# pipeline takes them in the order it runs them, and a reader wants the same
# phrasing whichever format they are looking at.
_ROLE_ORDER: tuple[ModelRole, ...] = (
    ModelRole.GENERATION,
    ModelRole.IMAGE_GENERATION,
)


def _availability(session: Session, fmt: Format) -> tuple[bool, str | None]:
    """Whether this format can run, and the one line saying why not.

    Every missing role is named, not the first one noticed. A format needing
    two of them reported only whichever `requires_roles` happened to list
    first, so selecting that one moved the reason to the other and read as the
    gate shifting rather than as half of it being met.
    """
    missing = [
        role
        for role in map(ModelRole, fmt.requires_roles)
        if session.get(SelectedModel, role) is None
    ]
    if missing:
        return False, _required(missing)
    if fmt.requires_voice:
        try:
            resolve_text_to_speech()
        except ModelResolutionError:
            return False, "Needs a voice model"
    return True, None


def _required(missing: list[ModelRole]) -> str:
    """"Needs a chat model and an image model", in a fixed reading order."""
    phrases = [_ROLE_PHRASES[role] for role in _ROLE_ORDER if role in missing]
    return f"Needs {' and '.join(phrases)}"
