"""Resolve ``@document`` / ``@folder`` mentions to the documents they point at.

Reference resolution, not retrieval: this answers "which knowledge-base
documents did the user point at this turn?". ``@document`` ids pass through;
``@folder`` ids expand to the documents directly inside each folder within this
workspace (direct children only, not nested subfolders). The caller turns the
returned ids into a retrieval ``SearchScope``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document


async def referenced_document_ids(
    session: AsyncSession,
    *,
    workspace_id: int,
    document_ids: list[int] | None = None,
    folder_ids: list[int] | None = None,
) -> tuple[int, ...]:
    """Sorted document ids the user pointed at (empty = nothing referenced)."""
    doc_ids = set(document_ids or [])
    folders = list(folder_ids or [])
    if folders:
        rows = await session.execute(
            select(Document.id).where(
                Document.workspace_id == workspace_id,
                Document.folder_id.in_(folders),
            )
        )
        doc_ids.update(rows.scalars().all())
    return tuple(sorted(doc_ids))


__all__ = ["referenced_document_ids"]
