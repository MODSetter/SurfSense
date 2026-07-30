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
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence.middleware import (
    ensure_folder_hierarchy,
)
from app.agents.chat.runtime.path_resolver import (
    PATH_MARKER,
    parse_documents_path,
    to_virtual_path,
    virtual_path_to_doc,
)
from app.db import Document, DocumentStatus, DocumentType, Workspace
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store.engines.base import Change
from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.write_lock import workspace_index_lock
from app.utils.document_converters import (
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)

# PATH_MARKER marks a row as living at a store path, i.e. owned by this indexer.
# Rows without it (Slack, Notion, the folder indexers) are never pruned.

_USER_AUTHOR = re.compile(r"<([^@>]+)@users\.surfsense>")


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
            )
    tracked = [entry.path for entry in await store.list_paths(head)]
    return _Plan(upserts=tracked, removals=[], tree=set(tracked))


async def _changes_since(
    store: KnowledgeStore, head: str, since: str
) -> list[Change] | None:
    """Net change set from ``since`` (exclusive) to ``head``, newest write wins.

    ``None`` when ``since`` is not in the history any more, which asks the caller
    for a full rebuild rather than a guess. Folding every revision in between
    matters because a queued task can be two commits behind by the time it runs.

    ``ponytail:`` walks the whole revision list to locate ``since``; upgrade path
    is a bounded walk once histories get long enough to notice.
    """
    ids = [revision.id for revision in await store.list_revisions()]
    if since not in ids:
        return None
    newer = ids[: ids.index(since)]
    merged: dict[str, Change] = {}
    for revision_id in reversed(newer):
        for change in await store.list_changes(revision_id):
            merged[change.path] = change
    return list(merged.values())


async def _converge(
    session: AsyncSession,
    store: KnowledgeStore,
    workspace: Workspace,
    head: str,
    plan: _Plan,
) -> IndexOutcome:
    outcome = IndexOutcome(revision=head)
    owned = await _load_owned(session, workspace.id)
    author_id = await _revision_author_id(store, head, workspace)

    for store_path in plan.upserts:
        virtual_path = to_virtual_path(store_path)
        content = await _read_indexable(store, head, store_path)
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
        outcome.deleted += await _delete(
            session, workspace.id, to_virtual_path(store_path), owned
        )

    if plan.tree is not None:
        live = {to_virtual_path(path) for path in plan.tree}
        outcome.deleted += await _prune(session, owned, live)

    # A failed document must not advance the marker, or the drift sweep can never
    # re-drive it. An intentional skip (unreadable blob) must not block it, or one
    # bad file wedges the workspace into rebuilding itself forever.
    if outcome.failed == 0:
        workspace.last_indexed_revision = head
        outcome.stamped = True
    await session.commit()
    return outcome


async def _read_indexable(
    store: KnowledgeStore, revision: str, store_path: str
) -> str | None:
    """Decoded, non-blank text of a blob, or ``None`` when it can't be indexed.

    One unusable blob must not strand every other document in the revision, and
    both cases here are legal git: ``touch``ed files and binaries.
    """
    try:
        raw = await store.read_as_of(revision, store_path)
    except Exception:
        logger.warning("Skipping unreadable path %s", store_path, exc_info=True)
        return None
    try:
        content = raw.decode()
    except UnicodeDecodeError:
        logger.info("Skipping undecodable blob at %s", store_path)
        return None
    if not content.strip():
        logger.info("Skipping blank document at %s", store_path)
        return None
    return content


async def _index_one(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
    content: str,
    author_id: str,
    owned: dict[str, Document],
) -> bool:
    """Upsert the row for one path, then hand it to the indexing pipeline."""
    folder_parts, title = parse_documents_path(virtual_path)
    if not title:
        logger.info("Skipping path with no document name: %s", virtual_path)
        return True

    document = await _resolve(session, workspace_id, virtual_path, owned)
    folder_id = await ensure_folder_hierarchy(
        session,
        workspace_id=workspace_id,
        created_by_id=author_id,
        folder_parts=folder_parts,
    )
    metadata = {**(document.document_metadata or {} if document else {})}
    metadata[PATH_MARKER] = virtual_path

    if document is None:
        document = Document(
            title=title,
            document_type=DocumentType.NOTE,
            document_metadata=metadata,
            content=content,
            content_hash=generate_content_hash(content, workspace_id),
            unique_identifier_hash=generate_unique_identifier_hash(
                DocumentType.NOTE, virtual_path, workspace_id
            ),
            source_markdown=content,
            workspace_id=workspace_id,
            folder_id=folder_id,
            created_by_id=author_id,
            status=DocumentStatus.pending(),
            updated_at=datetime.now(UTC),
        )
        session.add(document)
    else:
        # Update in place. No collision guard here: a hash hit is this path's
        # normal update case, not an error.
        document.title = title
        document.folder_id = folder_id
        document.source_markdown = content
        document.content_hash = generate_content_hash(content, workspace_id)
        document.document_metadata = metadata
        document.updated_at = datetime.now(UTC)

    # index() needs a persisted row and its id.
    await session.flush()

    connector_doc = ConnectorDocument(
        title=title,
        source_markdown=content,
        unique_id=virtual_path,
        document_type=document.document_type,
        workspace_id=workspace_id,
        created_by_id=str(document.created_by_id or author_id),
        connector_id=document.connector_id,
        metadata=metadata,
        folder_id=folder_id,
    )
    indexed = await IndexingPipelineService(session).index(document, connector_doc)
    if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
        logger.warning(
            "Indexing failed for %s: %s",
            virtual_path,
            (indexed.status or {}).get("reason"),
        )
        # index() rolls back on failure, which un-persists a row this run created.
        # Leaving it in the owned set would hand prune a transient object.
        owned.pop(virtual_path, None)
        return False

    # Recorded only once index() has committed it, so every entry is a real row.
    owned[virtual_path] = document
    return True


async def _resolve(
    session: AsyncSession,
    workspace_id: int,
    virtual_path: str,
    owned: dict[str, Document],
) -> Document | None:
    """Find the row that already represents ``virtual_path``, if any.

    Uploads reach git through the recorder while their row keeps the identity the
    upload gave it (``FILE:<filename>``), so a NOTE-hash-only lookup would insert
    a second row for content that already has one — the same file twice in the
    tree and twice in search. Adopt whatever is already there instead.
    """
    marked = owned.get(virtual_path)
    if marked is not None:
        return marked

    unique_hash = generate_unique_identifier_hash(
        DocumentType.NOTE, virtual_path, workspace_id
    )
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.unique_identifier_hash == unique_hash,
        )
    )
    document = result.scalar_one_or_none()
    if document is not None:
        return document

    return await virtual_path_to_doc(
        session, workspace_id=workspace_id, virtual_path=virtual_path
    )


async def _delete(
    session: AsyncSession,
    workspace_id: int,
    virtual_path: str,
    owned: dict[str, Document],
) -> int:
    """Drop the document at a removed path; its chunks cascade."""
    document = await _resolve(session, workspace_id, virtual_path, owned)
    if document is None:
        return 0
    marker = (document.document_metadata or {}).get(PATH_MARKER)
    if marker and marker != virtual_path:
        # The row moved, it did not go away. A rename arrives as a removal of the
        # old path plus an upsert of the new one, and the upsert has already
        # claimed this row; deleting on the removal would drop what the same run
        # just wrote. Reachable because a retitle moves the marker and leaves
        # unique_identifier_hash — which _resolve falls back to — on the old path.
        return 0
    owned.pop(virtual_path, None)
    await session.delete(document)
    return 1


async def _prune(
    session: AsyncSession, owned: dict[str, Document], live: set[str]
) -> int:
    """Delete indexer-owned rows whose path is no longer in the tree.

    Scoped to the marker, never to the workspace: connector rows (Slack, Notion,
    the folder indexers) have no path in the tree at all, and a workspace-wide
    prune would delete every one of them on the first rebuild.
    """
    deleted = 0
    for virtual_path, document in list(owned.items()):
        if virtual_path in live:
            continue
        await session.delete(document)
        owned.pop(virtual_path, None)
        deleted += 1
    return deleted


async def _load_owned(session: AsyncSession, workspace_id: int) -> dict[str, Document]:
    """Indexer-owned rows for a workspace, keyed by the path they live at."""
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_metadata[PATH_MARKER].as_string().is_not(None),
        )
    )
    owned: dict[str, Document] = {}
    for document in result.scalars():
        marker = (document.document_metadata or {}).get(PATH_MARKER)
        if marker:
            owned[marker] = document
    return owned


async def _revision_author_id(
    store: KnowledgeStore, revision: str, workspace: Workspace
) -> str:
    """Actor for rows this run creates, derived from git — never passed in.

    A caller-supplied id would be erased by the next :func:`index_tree`, making
    the two paths disagree. Autonomous agent writes author as the agent, which carries no
    user id, so those fall back to the workspace owner: ``created_by_id`` is
    required and rejects blanks, and agent writes are the whole point of indexing.
    """
    owner = str(workspace.user_id)
    try:
        revisions = await store.list_revisions(limit=1)
    except Exception:
        logger.warning("Could not read revision author for %s", revision, exc_info=True)
        return owner
    if not revisions:
        return owner
    return _author_user_id(revisions[0].author) or owner


def _author_user_id(author: str) -> str | None:
    """User id encoded in a revision author, or ``None`` for the agent."""
    match = _USER_AUTHOR.search(author or "")
    if match is None:
        return None
    try:
        return str(uuid.UUID(match.group(1)))
    except ValueError:
        return None
