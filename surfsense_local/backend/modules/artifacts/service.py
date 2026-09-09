import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS, FORMATS_BY_KEY, Format
from modules.artifacts.models import Artifact
from modules.artifacts.schemas import FormatRead, StudioJobCreate
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.queue import huey
from modules.llm.credentials import read_provider_key
from modules.llm.models import ModelRole, SelectedModel
from modules.workspaces.models import Workspace

logger = logging.getLogger(__name__)


def list_formats(session: Session) -> list[FormatRead]:
    """The catalog, each marked usable or not for the current setup."""
    return [
        FormatRead(
            key=fmt.key,
            label=fmt.label,
            requires_key=fmt.requires_key,
            available=_available(session, fmt),
        )
        for fmt in FORMATS
    ]


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
    if fmt.requires_key and not _available(session, fmt):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{fmt.label} needs an OpenRouter API key; set one in model settings",
        )
    if session.get(SelectedModel, ModelRole.GENERATION) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no generation model selected")

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


def enqueue_stranded_studio_jobs(
    session: Session, *, include_processing: bool = False
) -> None:
    """Put leftover Studio rows back on the queue if Huey no longer has them.

    The API commits the artifact, then enqueues. Huey pops a task when the
    worker takes it. Delete, a worker death, or a failed enqueue leaves a
    pending row and an empty queue — opening Studio or starting the worker
    puts those ids back, once.
    """
    statuses = [DocumentStatus.PENDING]
    if include_processing:
        statuses.append(DocumentStatus.PROCESSING)

    queued = _queued_studio_ids()
    artifacts = session.scalars(
        select(Artifact)
        .join(Document, Document.id == Artifact.document_id)
        .where(
            Document.document_type == DocumentType.ARTIFACT,
            Document.status.in_(statuses),
        )
        .order_by(Artifact.created_at.asc())
    ).all()

    to_run: list[int] = []
    for artifact in artifacts:
        if artifact.id in queued:
            continue
        if artifact.document.status is DocumentStatus.PROCESSING:
            artifact.document.status = DocumentStatus.PENDING
        to_run.append(artifact.id)
    if not to_run:
        return
    session.commit()
    for artifact_id in to_run:
        studio_job(artifact_id)
    logger.info("studio: requeued stranded artifacts %s", to_run)


def _queued_studio_ids() -> set[int]:
    ids: set[int] = set()
    for job in (*huey.pending(), *huey.scheduled()):
        if not job.name.endswith("studio_job") or not job.args:
            continue
        ids.add(job.args[0])
    return ids


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


def _available(session: Session, fmt: Format) -> bool:
    if not fmt.requires_key:
        return True
    return read_provider_key(session, "openrouter") is not None
