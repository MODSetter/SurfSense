"""Rows for the UI, written at commit time instead of at index time.

The sidebar needs a ``documents`` row, and its id, before it can show a note.
Building that row inside the indexer put it behind chunking, embedding and a
queue hop; this writes it from the commit's own change list instead, and leaves
chunks and vectors to the indexer.

Best effort: the indexer converges the same rows through the same primitives, so
a projection that is skipped or fails costs freshness, never correctness. It
never stamps ``last_indexed_revision`` — the content is not indexed yet, and
saying otherwise would make the drift sweep skip the workspace.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.folders import reconcile_tree_folders
from app.knowledge_store.index.rows import (
    delete_row,
    follow_rename,
    load_owned,
    read_indexable,
    revision_author_id,
    upsert_row,
)
from app.knowledge_store.locks import (
    KnowledgeStoreLockError,
    workspace_index_lock,
)
from app.knowledge_store.paths import to_virtual_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectedDocument:
    """One row the projection touched, captured before the session expires it."""

    id: int
    title: str
    folder_id: int | None
    virtual_path: str


@dataclass
class Projection:
    """What one revision did to the rows the UI reads."""

    created: list[ProjectedDocument] = field(default_factory=list)
    updated: list[ProjectedDocument] = field(default_factory=list)
    deleted: list[ProjectedDocument] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


async def project_revision(
    session: AsyncSession, workspace_id: int | str, revision: str
) -> Projection:
    """Mirror one revision's changes into ``documents``/``folders`` rows.

    Returns what changed so the caller can announce it. An empty result means
    either nothing to project or a projection that stood aside; the caller cannot
    tell the two apart, and does not need to — the indexer is the authority
    either way.
    """
    try:
        numeric = int(workspace_id)
    except (TypeError, ValueError):
        # Non-numeric ids exist only in tests, which have no row to project onto.
        return Projection()

    store = KnowledgeStore.for_workspace(workspace_id)
    try:
        async with workspace_index_lock(workspace_id):
            return await _project(session, store, numeric, revision)
    except KnowledgeStoreLockError:
        # A rebuild holds the lock. It is already writing these rows, so waiting
        # would only delay the turn to do work twice.
        logger.info(
            "Skipping projection for workspace %s: indexer holds the lock",
            workspace_id,
        )
        return Projection()
    except Exception:
        logger.warning(
            "Projection failed for workspace %s revision %s",
            workspace_id,
            revision,
            exc_info=True,
        )
        # The session is the caller's; hand it back usable rather than mid-abort.
        with suppress(Exception):
            await session.rollback()
        return Projection()


async def _project(
    session: AsyncSession, store: KnowledgeStore, workspace_id: int, revision: str
) -> Projection:
    projection = Projection()
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        logger.warning("Workspace %s no longer exists; not projecting", workspace_id)
        return projection

    changes = await store.list_changes(revision)
    owned = await load_owned(session, workspace.id)
    author_id = await revision_author_id(store, revision, workspace)

    for change in changes:
        if change.kind == "renamed" and change.previous_path:
            follow_rename(
                owned,
                workspace.id,
                to_virtual_path(change.previous_path),
                to_virtual_path(change.path),
            )

    for change in changes:
        virtual_path = to_virtual_path(change.path)
        if change.kind == "removed":
            removed = await delete_row(session, workspace.id, virtual_path, owned)
            if removed is not None:
                projection.deleted.append(_snapshot(removed, virtual_path))
            continue

        # ponytail: reads this revision, not HEAD, so a commit that lands
        # while a turn is ending can be projected stale for a moment. The
        # indexer converges to HEAD right after and corrects it.
        content = await read_indexable(store, revision, change.path)
        if content is None:
            continue
        upserted = await upsert_row(
            session,
            workspace_id=workspace.id,
            virtual_path=virtual_path,
            content=content,
            author_id=author_id,
            owned=owned,
        )
        if upserted is None:
            continue
        document, created = upserted
        bucket = projection.created if created else projection.updated
        bucket.append(_snapshot(document, virtual_path))

    # An empty folder rides in this revision only as its ``.keep``, which the
    # change loop skips as a blank document; reconcile from the tree so the
    # sidebar gets its folder row at commit time, not only once the indexer runs.
    await reconcile_tree_folders(
        session,
        store,
        revision,
        workspace_id=workspace.id,
        author_id=author_id,
    )

    await session.commit()
    return projection


def _snapshot(document, virtual_path: str) -> ProjectedDocument:
    """Copy the fields the caller needs while the instance is still loaded.

    ``session.commit()`` expires every instance, and a deleted one cannot be
    refreshed at all, so the read has to happen before the commit.
    """
    return ProjectedDocument(
        id=document.id,
        title=document.title,
        folder_id=document.folder_id,
        virtual_path=virtual_path,
    )
