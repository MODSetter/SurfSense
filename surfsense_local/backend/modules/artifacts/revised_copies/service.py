"""Create a revised copy's version: v1 from a source's file, or the next from its newest.

Commits before enqueueing: the worker is another process and must find the row.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.revision import (
    REVISION_KEY,
    Action,
    pending_revision,
)
from modules.artifacts.revised_copies.source_file import SourceFile
from modules.artifacts.revised_copies.versions import RevisionBase
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
)
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import EmbeddingNotChosenError, require_active_index

logger = logging.getLogger(__name__)


def revised_title(source_name: str) -> str:
    return f"{Path(source_name).stem} (revised)"


def create_revised_copy(
    session: Session,
    workspace_id: int,
    source: SourceFile,
    *,
    source_sha256: str,
    operations: list[dict[str, Any]],
    chat_thread_id: int | None,
) -> Artifact:
    """v1: the source's file with the operations applied, a new artifact derived from it.

    `source_sha256` is the file as checked; the job refuses bytes that differ.
    """
    revision = pending_revision(
        derived_from_document_id=source.document_id,
        source_name=source.path.name,
        source_sha256=source_sha256,
        base_number=None,
        action="edit",
        operations=operations,
        internal_comment_ids=[],
    )
    return _create(
        session,
        workspace_id,
        title=revised_title(source.path.name),
        format=source.format.format,
        base=None,
        source_ids=[source.document_id],
        revision=revision,
        chat_thread_id=chat_thread_id,
    )


def create_next_version(
    session: Session,
    workspace_id: int,
    base: RevisionBase,
    *,
    action: Action,
    operations: list[dict[str, Any]],
    chat_thread_id: int | None,
) -> Artifact:
    """The next version, made from the newest ready one by edits or by accepting or rejecting all."""
    revision = pending_revision(
        derived_from_document_id=base.revision["derived_from_document_id"],
        source_name=base.revision["source_name"],
        source_sha256=None,
        base_number=base.version.number,
        action=action,
        operations=operations,
        # Comment ids are never renumbered, so the base's internal ones stay internal.
        internal_comment_ids=list(base.revision.get("internal_comment_ids") or []),
    )
    meta = base.artifact.artifact_metadata or {}
    return _create(
        session,
        workspace_id,
        title=base.artifact.document.title,
        format=base.artifact.format,
        base=base,
        source_ids=list(meta.get("source_document_ids") or []),
        revision=revision,
        chat_thread_id=chat_thread_id,
    )


def _create(
    session: Session,
    workspace_id: int,
    *,
    title: str,
    format: str,
    base: RevisionBase | None,
    source_ids: list[int],
    revision: dict[str, Any],
    chat_thread_id: int | None,
) -> Artifact:
    # The job indexes the revised text; failing there would apply the edits twice.
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise RevisedCopyRefusedError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace_id,
        format=format,
        chat_thread_id=chat_thread_id,
    )
    session.add(artifact)
    session.flush()
    version = (
        ArtifactVersion(root=artifact.id, number=1, parent=None)
        if base is None
        else ArtifactVersion(
            root=base.version.root,
            number=next_version_number(session, workspace_id, base.version.root),
            parent=base.artifact.id,
        )
    )
    artifact.artifact_metadata = {
        "version": version.as_metadata(),
        "source_document_ids": source_ids,
        "spec": None,
        "prompt": None,
        REVISION_KEY: revision,
    }
    session.commit()
    studio_job(artifact.id)
    logger.info(
        "studio: enqueued revised copy %s action=%s root=%s v%s",
        artifact.id,
        revision["action"],
        version.root,
        version.number,
    )
    return artifact
