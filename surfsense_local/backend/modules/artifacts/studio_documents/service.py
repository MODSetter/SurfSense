"""Create the next version a Refine makes: pending, with the base's spec to rewrite."""

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.spec import DocumentSpec, document_spec
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
    version_of,
)
from modules.artifacts.studio_documents.recipe import RECIPE_KEY, refined
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures.layout import read_index
from modules.documents.source_figures.source import (
    kept_figures_dir,
    source_in_workspace,
)
from modules.embedding.active import require_active_index

logger = logging.getLogger(__name__)

_BUSY = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


def refinable_spec(session: Session, artifact_id: int) -> DocumentSpec:
    """The spec a Refine would rewrite, or the HTTP refusal saying why there is none."""
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
    # The job indexes the new version; failing there would spend the model call.
    require_active_index(session)
    if artifact.document.status in _BUSY:
        raise HTTPException(status.HTTP_409_CONFLICT, "already generating")
    spec = document_spec(artifact.artifact_metadata)
    if spec is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only a Word document or PDF made in Studio or by the agent can be refined.",
        )
    return spec


def figure_captions(session: Session, artifact_id: int) -> list[str | None]:
    """The captions of the figures a refine's prompt will list, read without side effects."""
    artifact = session.get(Artifact, artifact_id)
    captions: list[str | None] = []
    for document_id in (artifact.artifact_metadata or {}).get(
        "source_document_ids"
    ) or []:
        try:
            source = source_in_workspace(session, artifact.workspace_id, document_id)
        except LookupError:
            continue
        entries = read_index(kept_figures_dir(source)) or []
        captions.extend(entry.get("caption") for entry in entries)
    return captions


def create_refine_version(
    session: Session, artifact_id: int, instruction: str
) -> Artifact:
    """The base's next version, pending until Studio's job rewrites and renders it.

    Commits before enqueueing: the worker is another process and must find the row.
    """
    spec = refinable_spec(session, artifact_id)
    base = session.get(Artifact, artifact_id)
    assert base is not None  # refinable_spec found it
    base_version = version_of(base.artifact_metadata) or ArtifactVersion(
        root=base.id, number=1, parent=None
    )
    meta = base.artifact_metadata or {}

    document = Document(
        workspace_id=base.workspace_id,
        title=base.document.title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id, workspace_id=base.workspace_id, format=base.format
    )
    session.add(artifact)
    session.flush()
    version = ArtifactVersion(
        root=base_version.root,
        number=next_version_number(session, base.workspace_id, base_version.root),
        parent=base.id,
    )
    artifact.artifact_metadata = {
        RECIPE_KEY: refined(instruction, spec),
        "version": version.as_metadata(),
        "source_document_ids": list(meta.get("source_document_ids") or []),
        "prompt": meta.get("prompt"),
    }
    session.commit()
    studio_job(artifact.id)
    logger.info(
        "studio: enqueued refine %s of %s root=%s v%s",
        artifact.id,
        base.id,
        version.root,
        version.number,
    )
    return artifact
