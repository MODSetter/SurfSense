"""Derive ``folders`` rows from the tree, and prune the ones no path needs.

A folder row must exist for every ancestor of a stored file, and for a folder
that holds a ``.keep`` marker (an explicitly-created empty folder). A row with
neither is pruned — the Phase-6 gap where an emptied folder lingered.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Folder
from app.knowledge_store.paths import (
    StorePath,
    StorePathError,
    safe_folder_segment,
)
from app.services.folder_service import ensure_folder_hierarchy

if TYPE_CHECKING:
    from app.knowledge_store import KnowledgeStore


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
        (
            await session.execute(
                select(Folder).where(Folder.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    by_id = {folder.id: folder for folder in rows}
    stale = [f for f in rows if _chain_of(f, by_id) not in live]
    for folder in sorted(stale, key=lambda f: len(_chain_of(f, by_id)), reverse=True):
        await session.delete(folder)
    return len(stale)


async def reconcile_tree_folders(
    session: AsyncSession,
    store: KnowledgeStore,
    revision: str,
    *,
    workspace_id: int,
    author_id: str | None,
) -> int:
    """Reconcile ``folders`` against the whole tree at ``revision``.

    An empty folder rides in the tree only as its ``.keep``, a blank blob the
    incremental change list drops; reconciling from the tree snapshot rather than
    the changes is what lets the incremental and projection paths derive the same
    folder rows the full rebuild does.
    """
    tracked = [
        entry.path
        for entry in await store.list_paths(revision)
        if entry.path.strip("/").startswith("documents/")
    ]
    return await reconcile_folders(
        session,
        workspace_id=workspace_id,
        live=live_folder_chains(tracked),
        author_id=author_id,
    )


async def reparent_folder(
    session: AsyncSession,
    *,
    workspace_id: int,
    source_chain: tuple[str, ...],
    destination_chain: tuple[str, ...],
    author_id: str | None,
) -> bool:
    """Move the folder row at ``source_chain`` to ``destination_chain`` in place.

    Renaming the row instead of prune-then-create keeps its id, so citations and
    child rows (which follow ``parent_id``) survive a rename or reparent. The
    caller runs this before :func:`reconcile_folders`, which then finds the row
    already at the live chain and leaves it alone. Returns ``False`` when no row
    holds the source — an implied folder with no explicit row, which the tree
    reconcile handles on its own.
    """
    if not source_chain or not destination_chain:
        return False
    rows = (
        (
            await session.execute(
                select(Folder).where(Folder.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    by_id = {folder.id: folder for folder in rows}
    moving = next((f for f in rows if _chain_of(f, by_id) == source_chain), None)
    if moving is None:
        return False
    parent_id = await ensure_folder_hierarchy(
        session,
        workspace_id=workspace_id,
        created_by_id=author_id,
        folder_parts=list(destination_chain[:-1]),
    )
    moving.name = destination_chain[-1]
    moving.parent_id = parent_id
    return True


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
