"""Resolve ``@document`` ids into references for the pointer block."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import PathIndex, doc_to_virtual_path
from app.db import Document

from .models import ReferenceKind, ResolvedReference


async def resolve_document_references(
    session: AsyncSession,
    *,
    search_space_id: int,
    document_ids: list[int],
    index: PathIndex,
) -> list[ResolvedReference]:
    """Map document ids to references in input order; unknown ids are dropped.

    Best-effort and fail-closed: an id outside ``search_space_id`` (deleted or
    foreign) simply does not produce a reference.
    """
    if not document_ids:
        return []

    rows = await session.execute(
        select(Document).where(
            Document.search_space_id == search_space_id,
            Document.id.in_(document_ids),
        )
    )
    documents_by_id = {row.id: row for row in rows.scalars().all()}

    references: list[ResolvedReference] = []
    for document_id in dict.fromkeys(document_ids):
        document = documents_by_id.get(document_id)
        if document is None:
            continue
        title = str(document.title or "untitled")
        references.append(
            ResolvedReference(
                kind=ReferenceKind.DOCUMENT,
                entity_id=document.id,
                label=title,
                path=doc_to_virtual_path(
                    doc_id=document.id,
                    title=title,
                    folder_id=document.folder_id,
                    index=index,
                ),
            )
        )
    return references


__all__ = ["resolve_document_references"]
