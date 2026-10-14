"""A revised copy's versions, and the one its next version starts from: the newest ready one."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.revised_copies.formats import RevisableFormat, revisable_format
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.script_documents.version import ArtifactVersion, version_of
from modules.documents.models import Document, DocumentStatus
from shared.config import get_storage_settings

IN_FLIGHT = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


@dataclass(frozen=True)
class RevisionBase:
    artifact: Artifact
    version: ArtifactVersion
    revision: dict[str, Any]
    path: Path  # the base version's primary file
    format: RevisableFormat


def revision_base(
    session: Session, workspace_id: int, artifact_id: int
) -> RevisionBase:
    """The newest ready version of the revised copy `artifact_id` belongs to.

    Any version names the copy: an edit always continues from the newest, so no
    change is lost to an edit of an older one. One version is made at a time.
    """
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise RevisedCopyRefusedError(
            f"There is no artifact {artifact_id} in this workspace."
        )
    version = version_of(artifact.artifact_metadata)
    if revision_of(artifact.artifact_metadata) is None or version is None:
        raise RevisedCopyRefusedError(
            f"Artifact {artifact_id} is not a revised copy of a source file. To "
            "change a document you rendered, render it again with its artifact_id."
        )
    versions = versions_of(session, workspace_id, version.root)
    running = next((v for v in versions if v.document.status in IN_FLIGHT), None)
    if running is not None:
        raise RevisedCopyRefusedError(
            f"Version {_number(running)} of this revised copy is still being made. "
            "Wait for it to finish, then revise again."
        )
    newest = next(
        (v for v in versions if v.document.status is DocumentStatus.READY), None
    )
    if newest is None:
        raise RevisedCopyRefusedError(
            f"Artifact {artifact_id}'s revised copy has no ready version to revise. "
            "Revise the source file again with document_id."
        )
    revision = revision_of(newest.artifact_metadata) or {}
    newest_version = version_of(newest.artifact_metadata)
    path = primary_path(newest)
    fmt = revisable_format(revision.get("source_name", ""))
    if path is None or fmt is None or newest_version is None:
        raise RevisedCopyRefusedError(
            f"The file of artifact {newest.id} is missing, so it cannot be revised."
        )
    return RevisionBase(newest, newest_version, revision, path, fmt)


def versions_of(session: Session, workspace_id: int, root: int) -> list[Artifact]:
    """Every version of a root, newest first."""
    version = Artifact.artifact_metadata["version"]
    return list(
        session.scalars(
            select(Artifact)
            .join(Document, Document.id == Artifact.document_id)
            .where(
                Artifact.workspace_id == workspace_id,
                version["root"].as_integer() == root,
            )
            .order_by(version["number"].as_integer().desc())
        )
    )


def version_numbered(
    session: Session, workspace_id: int, root: int, number: int
) -> Path | None:
    """The primary file of a root's ready version `number`, or None when it is gone."""
    found = next(
        (
            v
            for v in versions_of(session, workspace_id, root)
            if _number(v) == number and v.document.status is DocumentStatus.READY
        ),
        None,
    )
    return primary_path(found) if found is not None else None


def primary_path(artifact: Artifact) -> Path | None:
    """The version's primary file on disk, or None when it is gone."""
    primary = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    if primary is None:
        return None
    path = get_storage_settings().data_dir / primary.storage_key
    return path if path.is_file() else None


def _number(artifact: Artifact) -> int:
    version = version_of(artifact.artifact_metadata)
    return version.number if version is not None else 0
