"""Derive ``folders`` rows from the tree, and prune the ones no path needs.

A folder row must exist for every ancestor of a stored file, and for a folder
that holds a ``.keep`` marker (an explicitly-created empty folder). A row with
neither is pruned — the Phase-6 gap where an emptied folder lingered.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Folder
from app.knowledge_store.paths import (
    StorePath,
    StorePathError,
    safe_folder_segment,
)
from app.services.folder_service import ensure_folder_hierarchy


def live_folder_chains(store_paths: Iterable[str]) -> set[tuple[str, ...]]:
    """Folder chains a row must exist for, ``.keep`` folders included.

    Each file contributes its ancestors; segments are normalized to the names
    ``ensure_folder_hierarchy`` writes, so the sets compare equal.
    """
    chains: set[tuple[str, ...]] = set()
    for store_path in store_paths:
        try:
            segments = StorePath.from_store(store_path).segments
        except StorePathError:
            continue
        folders = tuple(safe_folder_segment(s) for s in segments[:-1])
        for depth in range(1, len(folders) + 1):
            chains.add(folders[:depth])
    return chains


async def reconcile_folders(
    session: AsyncSession,
    *,
    workspace_id: int,
    live: set[tuple[str, ...]],
    author_id: str | None,
) -> int:
    """Make the ``folders`` rows match ``live``; return how many were pruned.

    A live chain's ancestors are all live, so pruning never removes a row a
    document still needs; deletion is leaf-first so a cascade cannot surprise a
    row still queued for its own delete.
    """
    for chain in sorted(live, key=len):
        await ensure_folder_hierarchy(
            session,
            workspace_id=workspace_id,
            created_by_id=author_id,
            folder_parts=list(chain),
        )
    rows = (
        (await session.execute(select(Folder).where(Folder.workspace_id == workspace_id)))
        .scalars()
        .all()
    )
    by_id = {folder.id: folder for folder in rows}
    stale = [f for f in rows if _chain_of(f, by_id) not in live]
    for folder in sorted(stale, key=lambda f: len(_chain_of(f, by_id)), reverse=True):
        await session.delete(folder)
    return len(stale)


def _chain_of(folder: Folder, by_id: dict[int, Folder]) -> tuple[str, ...]:
    """The folder's name path from the root, following ``parent_id``."""
    parts: list[str] = []
    cursor: Folder | None = folder
    seen: set[int] = set()
    while cursor is not None and cursor.id not in seen:
        seen.add(cursor.id)
        parts.append(cursor.name)
        cursor = by_id.get(cursor.parent_id)
    parts.reverse()
    return tuple(parts)
