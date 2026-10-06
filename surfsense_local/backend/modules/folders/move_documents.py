from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.documents.models import Document
from modules.folders.models import Folder
from modules.folders.schemas import MoveOutcome, SkippedMove


def move_documents(
    session: Session, folder: Folder, document_ids: list[int]
) -> MoveOutcome:
    """File sources in `folder`. A source whose bytes already sit there stays put.

    Dedup is per folder, so a move must not make two copies of one file there.
    """
    wanted = list(dict.fromkeys(document_ids))
    documents = {
        document.id: document
        for document in session.scalars(
            select(Document).where(
                Document.id.in_(wanted),
                Document.workspace_id == folder.workspace_id,
            )
        )
    }
    if len(documents) != len(wanted):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "a chosen source is not in this workspace",
        )
    keys = {d.dedup_key for d in documents.values() if d.dedup_key is not None}
    held = dict(
        session.execute(
            select(Document.dedup_key, Document.id).where(
                Document.folder_id == folder.id, Document.dedup_key.in_(keys)
            )
        ).all()
    )

    moved: list[int] = []
    skipped: list[SkippedMove] = []
    for document_id in wanted:
        document = documents[document_id]
        twin = held.get(document.dedup_key) if document.dedup_key else None
        if twin is not None and twin != document.id:
            skipped.append(
                SkippedMove(
                    document_id=document.id, reason="duplicate", duplicate_of=twin
                )
            )
            continue
        document.folder_id = folder.id
        if document.dedup_key is not None:
            held[document.dedup_key] = document.id
        moved.append(document.id)
    session.flush()
    return MoveOutcome(moved=moved, skipped=skipped)
