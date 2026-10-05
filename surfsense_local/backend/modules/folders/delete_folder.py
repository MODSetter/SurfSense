import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.models import Folder, FolderState
from modules.folders.schemas import FolderSummary
from modules.folders.tree import subtree_ids
from shared.config import get_storage_settings

# Each batch is its own transaction, so no delete holds SQLite's write lock past
# the 5 s busy timeout a concurrent note write waits for.
BATCH = 500


def summarize(session: Session, folder: Folder) -> FolderSummary:
    folders = subtree_ids(session, [folder.id])
    counts = dict(
        session.execute(
            select(Document.document_type, func.count())
            .where(Document.folder_id.in_(folders))
            .group_by(Document.document_type)
        ).all()
    )
    return FolderSummary(
        folders=len(folders) - 1,
        sources=counts.get(DocumentType.FILE, 0) + counts.get(DocumentType.NOTE, 0),
        artifacts=counts.get(DocumentType.ARTIFACT, 0),
    )


def delete_folder(session: Session, folder: Folder) -> tuple[list[int], list[int]]:
    """Delete a folder, its subfolders and every source in them, for good.

    The subtree leaves every scope and the tree first, then documents go in
    batches with their bytes, then the folders. Answers the deleted document
    and folder ids.
    """
    if folder.parent_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a root's own folder cannot be deleted"
        )
    folders = subtree_ids(session, [folder.id])
    busy = session.scalar(
        select(func.count()).where(
            Document.folder_id.in_(folders),
            Document.status == DocumentStatus.PROCESSING,
        )
    )
    if busy:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{busy} sources in this folder are still being read; "
            "wait for them or stop them first",
        )
    session.execute(
        update(Folder).where(Folder.id.in_(folders)).values(state=FolderState.DELETING)
    )
    # A queued read the worker reaches mid-delete would turn processing, outlive
    # its batch and be left behind unfiled; cancelled, `begin_job` skips it.
    session.execute(
        update(Document)
        .where(
            Document.folder_id.in_(folders),
            Document.status == DocumentStatus.PENDING,
        )
        .values(status=DocumentStatus.CANCELLED)
    )
    session.commit()

    deleted: list[int] = []
    while batch := _next_batch(session, folders):
        directories = _directories(session, folder.workspace_id, batch)
        session.execute(
            delete(Document).where(
                Document.id.in_(batch), Document.status != DocumentStatus.PROCESSING
            )
        )
        session.commit()
        for directory in directories:
            shutil.rmtree(directory, ignore_errors=True)
        deleted.extend(batch)

    # Children cascade from the top folder.
    session.execute(delete(Folder).where(Folder.id == folder.id))
    session.commit()
    return deleted, folders


def _next_batch(session: Session, folders: list[int]) -> list[int]:
    return list(
        session.scalars(
            select(Document.id)
            .where(
                Document.folder_id.in_(folders),
                Document.status != DocumentStatus.PROCESSING,
            )
            .limit(BATCH)
        )
    )


def _directories(session: Session, workspace_id: int, batch: list[int]) -> list[Path]:
    """A source's bytes, and a filed Studio output's rendered blobs."""
    storage = get_storage_settings()
    directories = [storage.document_dir(workspace_id, i) for i in batch]
    artifact_ids = session.scalars(
        select(Artifact.id).where(Artifact.document_id.in_(batch))
    )
    directories += [storage.artifact_dir(workspace_id, i) for i in artifact_ids]
    return directories
