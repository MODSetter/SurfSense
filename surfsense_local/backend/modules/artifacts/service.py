import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS, FORMATS_BY_KEY, Format
from modules.artifacts.models import Artifact
from modules.artifacts.schemas import FormatRead, StudioJobCreate
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.models import ModelRole, SelectedModel
from modules.workspaces.models import Workspace

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
                requires_role=fmt.requires_role,
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

    documents = _resolve_sources(session, workspace, payload.document_ids)

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
            "options": payload.options,
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


def _resolve_sources(
    session: Session, workspace: Workspace, document_ids: list[int]
) -> list[Document]:
    if not document_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "pick at least one source"
        )
    documents = session.scalars(
        select(Document).where(
            Document.id.in_(document_ids),
            Document.workspace_id == workspace.id,
        )
    ).all()
    if len(documents) != len(set(document_ids)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "a chosen source is not in this workspace",
        )
    not_ready = [doc.id for doc in documents if doc.status is not DocumentStatus.READY]
    if not_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"sources are still indexing: {not_ready}",
        )
    return list(documents)


def _availability(session: Session, fmt: Format) -> tuple[bool, str | None]:
    if fmt.requires_role is None:
        return True, None
    role = ModelRole(fmt.requires_role)
    if session.get(SelectedModel, role) is not None:
        return True, None
    if role is ModelRole.IMAGE_GENERATION:
        return False, "Image model required"
    return False, "Chat model required"
