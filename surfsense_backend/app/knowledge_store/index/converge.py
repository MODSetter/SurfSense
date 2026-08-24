"""Postgres as a derived index of the store.

Git holds the content; ``documents`` + ``chunks`` are a rebuildable projection of
it. The two entry points differ only in scope: :func:`index_changes` folds in
what moved since the last run, :func:`index_tree` reconciles against the whole
tree and is therefore the only one that can notice a deletion it never saw.
Both run the same convergence body, so the two paths cannot drift apart.

Neither wipes. Document rows are upserted by path and keep their ids, because
``documents``/``folders`` replicate to the browser and an id that changed under
a reader would make every note vanish and reappear. Chunk rows are the
disposable layer, replaced per document by the existing indexing pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, Workspace
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.engines.base import Change
from app.knowledge_store.index.folders import reconcile_tree_folders
from app.knowledge_store.index.rows import (
    delete_row,
    follow_rename,
    load_owned,
    prune,
    read_indexable,
    revision_author_id,
    upsert_row,
)
from app.knowledge_store.locks import workspace_index_lock
from app.knowledge_store.paths import PATH_MARKER, to_virtual_path
from app.utils.document_converters import generate_content_hash

logger = logging.getLogger(__name__)

__all__ = ["PATH_MARKER", "IndexOutcome", "index_changes", "index_tree"]


@dataclass
class IndexOutcome:
    """What one convergence run did, and whether it may stamp the revision."""

    revision: str | None
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    deleted: int = 0
    stamped: bool = False

    def __str__(self) -> str:
        return (
            f"revision={self.revision} indexed={self.indexed} "
            f"skipped={self.skipped} failed={self.failed} "
            f"deleted={self.deleted} stamped={self.stamped}"
        )


@dataclass(frozen=True)
class _Plan:
    """Which store paths to converge, and whether to prune to the whole tree."""

    upserts: list[str]
    removals: list[str]
    #: Paths that moved, as ``(from, to)``; the row follows instead of being remade.
    renames: list[tuple[str, str]] = field(default_factory=list)
    #: Every path in the tree, when the run is a full rebuild; ``None`` otherwise.
    tree: set[str] | None = field(default=None)


async def index_changes(session: AsyncSession, workspace_id: int) -> IndexOutcome:
    """Fold the paths that moved since the last run into the index.

    Always converges to whatever HEAD is now, never to the revision that
    triggered the call: two saves in a row enqueue two tasks, the index lock
    serializes them without ordering them, and stamping the older id last would
    leave a stale index. Reading HEAD under the lock makes task order
    irrelevant, which is why no revision is passed in.
    """
    return await _run(session, workspace_id, full=False)


async def index_tree(session: AsyncSession, workspace_id: int) -> IndexOutcome:
    """Reconcile the index against every path in the tree (the Fossil rebuild).

    Distrusts the stamp, so this is the only path that removes a row whose file
    left the tree while the index was not watching — and the only repair for an
    index that fell behind in a way the change log can no longer describe.
    """
    return await _run(session, workspace_id, full=True)


async def _run(session: AsyncSession, workspace_id: int, *, full: bool) -> IndexOutcome:
    store = KnowledgeStore.for_workspace(workspace_id)
    async with workspace_index_lock(workspace_id):
        head = await store.get_current_revision()
        if head is None:
            return IndexOutcome(revision=None)

        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            logger.warning("Workspace %s no longer exists; not indexing", workspace_id)
            return IndexOutcome(revision=head)
        if not full and workspace.last_indexed_revision == head:
            return IndexOutcome(revision=head, stamped=True)

        since = None if full else workspace.last_indexed_revision
        plan = await _plan(store, head, since)
        outcome = await _converge(session, store, workspace, head, plan)

    logger.info("Knowledge store index for workspace %s: %s", workspace_id, outcome)
    return outcome


async def _plan(store: KnowledgeStore, head: str, since: str | None) -> _Plan:
    """Paths to converge: the changes since ``since``, else the whole tree."""
    if since is not None:
        changes = await _changes_since(store, head, since)
        if changes is not None:
            return _Plan(
                upserts=[c.path for c in changes if c.kind != "removed"],
                removals=[c.path for c in changes if c.kind == "removed"],
                renames=[
                    (c.previous_path, c.path)
                    for c in changes
                    if c.kind == "renamed" and c.previous_path
                ],
            )
    tracked = [entry.path for entry in await store.list_paths(head)]
    return _Plan(upserts=tracked, removals=[], tree=set(tracked))


async def _changes_since(
    store: KnowledgeStore, head: str, since: str
) -> list[Change] | None:
    """Net change set from ``since`` (exclusive) to ``head``.

    One diff of the two snapshots rather than a fold of each revision between
    them, which matters because a queued task can be several commits behind by
    the time it runs: a path written twice in that window appears once, a path
    written then deleted appears not at all, and a move is a single ``renamed``
    change that keeps both of its paths.

    ``None`` when ``since`` is not in the history any more, which asks the caller
    for a full rebuild rather than a guess.

    ``ponytail:`` walks the whole revision list to locate ``since``; upgrade path
    is a bounded walk once histories get long enough to notice.
    """
    ids = [revision.id for revision in await store.list_revisions()]
    if since not in ids:
        return None
    return await store.list_changes(head, since=since)


async def _converge(
    session: AsyncSession,
    store: KnowledgeStore,
    workspace: Workspace,
    head: str,
    plan: _Plan,
) -> IndexOutcome:
    outcome = IndexOutcome(revision=head)
    owned = await load_owned(session, workspace.id)
    author_id = await revision_author_id(store, head, workspace)

    for from_path, to_path in plan.renames:
        if _is_document_store_path(from_path) and _is_document_store_path(to_path):
            follow_rename(
                owned,
                workspace.id,
                to_virtual_path(from_path),
                to_virtual_path(to_path),
            )
        elif _is_document_store_path(from_path):
            removed = await delete_row(
                session, workspace.id, to_virtual_path(from_path), owned
            )
            outcome.deleted += 1 if removed is not None else 0

    for store_path in plan.upserts:
        if not _is_document_store_path(store_path):
            outcome.skipped += 1
            continue
        virtual_path = to_virtual_path(store_path)
        content = await read_indexable(store, head, store_path)
        if content is None:
            outcome.skipped += 1
            continue
        ready = await _index_one(
            session,
            workspace_id=workspace.id,
            virtual_path=virtual_path,
            content=content,
            author_id=author_id,
            owned=owned,
        )
        if ready:
            outcome.indexed += 1
        else:
            outcome.failed += 1

    for store_path in plan.removals:
        if _is_document_store_path(store_path):
            removed = await delete_row(
                session, workspace.id, to_virtual_path(store_path), owned
            )
        else:
            removed = None
        outcome.deleted += 1 if removed is not None else 0

    if plan.tree is not None:
        live_documents = {
            to_virtual_path(path) for path in plan.tree if _is_document_store_path(path)
        }
        outcome.deleted += await prune(session, owned, live_documents)

    # A failed document must not advance the marker, or the drift sweep can never
    # re-drive it. An intentional skip (unreadable blob) must not block it, or one
    # bad file wedges the workspace into rebuilding itself forever. Folders are
    # reconciled from the tree on both paths so an empty ``.keep`` folder gets its
    # row incrementally, not only on a full rebuild; a failed run left the session
    # mid-rollback, no state to finalize.
    if outcome.failed == 0:
        await reconcile_tree_folders(
            session,
            store,
            head,
            workspace_id=workspace.id,
            author_id=author_id,
        )
        workspace.last_indexed_revision = head
        outcome.stamped = True
    await session.commit()
    return outcome


async def _index_one(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
    content: str,
    author_id: str,
    owned: dict[str, Document],
) -> bool:
    """Upsert the row for one path, then index it in its own session.

    ``index`` rolls the shared session back on failure, which would discard the
    whole batch; giving each document its own session isolates that rollback.
    """
    # index_tree replays every path in the tree, so the hourly drift sweep would
    # re-embed rows that never changed. Read whether this row is already converged
    # before the upsert mutates it in place: a READY row whose body still hashes to
    # this content keeps its chunks, so only its path/folder need reconciling — the
    # cheap upsert always runs (a move updates it), the costly re-embed does not.
    settled = owned.get(virtual_path)
    already_indexed = (
        settled is not None
        and DocumentStatus.is_state(settled.status, DocumentStatus.READY)
        and settled.content_hash == generate_content_hash(content, workspace_id)
    )

    upserted = await upsert_row(
        session,
        workspace_id=workspace_id,
        virtual_path=virtual_path,
        content=content,
        author_id=author_id,
        owned=owned,
    )
    if upserted is None:
        return True
    document, _created = upserted

    if already_indexed:
        owned[virtual_path] = document
        return True

    connector_doc = ConnectorDocument(
        title=document.title,
        source_markdown=content,
        unique_id=virtual_path,
        document_type=document.document_type,
        workspace_id=workspace_id,
        created_by_id=str(document.created_by_id or author_id),
        connector_id=document.connector_id,
        metadata=document.document_metadata,
        folder_id=document.folder_id,
    )
    document_id = document.id

    # Commit so the per-document session can read the row on its own connection.
    await session.commit()

    from app.tasks.celery_tasks import get_celery_session_maker

    session_maker = get_celery_session_maker()
    async with session_maker() as doc_session:
        refetched = await doc_session.get(Document, document_id)
        if refetched is None:
            return False
        indexed = await IndexingPipelineService(doc_session).index(
            refetched, connector_doc
        )
        ready = DocumentStatus.is_state(indexed.status, DocumentStatus.READY)
        reason = None if ready else (indexed.status or {}).get("reason")

    # Pull back the status/chunks the other connection committed.
    await session.refresh(document)
    if not ready:
        logger.warning("Indexing failed for %s: %s", virtual_path, reason)
        owned.pop(virtual_path, None)
        return False

    owned[virtual_path] = document
    return True


def _is_document_store_path(path: str) -> bool:
    return path.strip("/").startswith("documents/")
