from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus


def load_selected_sources(
    session: Session, workspace_id: int, document_ids: Sequence[int]
) -> list[Document]:
    """The named documents, if they exist in this workspace and are ready to search."""
    unique = list(dict.fromkeys(document_ids))
    if not unique:
        return []
    documents = session.scalars(
        select(Document).where(
            Document.id.in_(unique),
            Document.workspace_id == workspace_id,
        )
    ).all()
    if len(documents) != len(unique):
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
    by_id = {doc.id: doc for doc in documents}
    return [by_id[document_id] for document_id in unique]
