"""Resolve ``@folder`` ids into references for the pointer block."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import DOCUMENTS_ROOT, PathIndex
from app.db import Folder

from .models import FolderReference


def folder_pointer_path(folder_id: int, folder_paths: dict[int, str]) -> str:
    """Trailing-slash virtual path so the model reads the pointer as a directory."""
    base = folder_paths.get(folder_id, DOCUMENTS_ROOT)
    return base if base.endswith("/") else f"{base}/"


async def resolve_folder_references(
    session: AsyncSession,
    *,
    search_space_id: int,
    folder_ids: list[int],
    index: PathIndex,
) -> list[FolderReference]:
    """Map folder ids to references in input order; unknown ids are dropped."""
    if not folder_ids:
        return []

    rows = await session.execute(
        select(Folder).where(
            Folder.search_space_id == search_space_id,
            Folder.id.in_(folder_ids),
        )
    )
    folders_by_id = {row.id: row for row in rows.scalars().all()}

    references: list[FolderReference] = []
    for folder_id in dict.fromkeys(folder_ids):
        folder = folders_by_id.get(folder_id)
        if folder is None:
            continue
        references.append(
            FolderReference(
                entity_id=folder.id,
                label=str(folder.name or "untitled"),
                path=folder_pointer_path(folder.id, index.folder_paths),
            )
        )
    return references


__all__ = ["folder_pointer_path", "resolve_folder_references"]
