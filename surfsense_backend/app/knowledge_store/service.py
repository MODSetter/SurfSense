"""Application service: document changes become knowledge-store revisions.

The one door for everything that is not an agent turn — editor saves,
upload-extracted markdown, connector sync batches, deletes, moves. Routes,
Celery tasks and other services call these verbs; none of them open a
transaction against the store themselves.

Callers hand over documents, never paths. Where a document's file lives is a
question only this module and the marker on the row can answer, and a caller
that recomputes it is a caller whose delete misses the file the agent named.

Every verb is a no-op on a workspace that is not git-backed, so callers do not
have to ask first. When a caller needs the answer for its own behaviour —
refusing an operation git cannot express, say —
:func:`app.knowledge_store.settings.knowledge_store_enabled_for` is the query.

Never raises. The Postgres write path coexists with the store until the
migration's cut, so a store that cannot be reached must not fail a mutation the
user already made; failures are logged and counted, and the drift check is what
notices.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    PATH_MARKER,
    PathIndex,
    build_path_index,
    doc_to_virtual_path,
    to_store_path,
    virtual_path_of,
)
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.index.queue import enqueue_index
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)
from app.observability import metrics

if TYPE_CHECKING:
    from app.db import Document

logger = logging.getLogger(__name__)


async def record_markdown_files(
    *,
    workspace_id: int | str,
    files: Mapping[str, str],
    message: str,
    author_user_id: str | None,
    removes: Sequence[str] = (),
    moves: Sequence[tuple[str, str]] = (),
) -> str | None:
    """Record ``files`` (store path → markdown) as one revision.

    ``removes`` drops paths in the same revision as the writes — otherwise a
    retitle would leave one document behind as two files. ``moves`` relocates a
    path whose content the caller does not have in hand, which is most of them:
    a folder rename moves every descendant without reading one.

    ``None`` when the store is disabled, the batch is empty, or nothing
    actually changed (identical content is a no-op by construction).
    """
    empty = not files and not removes and not moves
    if empty or not load_knowledge_store_settings().enabled:
        return None
    store = KnowledgeStore.for_workspace(workspace_id)
    async with store.transaction(
        message=message, author=user_identity(author_user_id)
    ) as tx:
        for path, markdown in files.items():
            tx.write(path, markdown.encode())
        for path in removes:
            tx.remove(path)
        for source, destination in moves:
            tx.move(source, destination)
    if tx.revision is not None:
        enqueue_index(workspace_id)
    return tx.revision


async def record_saved_document(
    session: AsyncSession,
    *,
    workspace_id: int,
    doc_id: int,
    title: str,
    folder_id: int | None,
    markdown: str,
    author_user_id: str | None,
    title_is_explicit: bool = False,
) -> str | None:
    """Resolve one document's canonical store path and record the save.

    The recorded path is remembered on the row (``document_metadata``), so the
    next save knows where the document used to live and can drop that file
    when a retitle moves it. The marker is written only when a revision was
    actually recorded: a marker without a file would make the row look
    indexer-owned and a later rebuild would prune it.

    ``title_is_explicit`` means someone chose the title, so the file follows it.
    A note's title is otherwise re-read from its first heading on every save,
    and letting that place the file would rename whatever the agent named — for
    a name the caller never asked to change.

    Never raises: while the store coexists with the Postgres write path
    (until the Phase 5 cut), a recording failure must not fail the save
    that already committed — it is logged instead.
    """
    if not await knowledge_store_enabled_for(workspace_id):
        return None
    try:
        index = await build_path_index(session, workspace_id)
        document = await session.get(Document, doc_id)
        metadata = document.document_metadata if document else None
        previous = (metadata or {}).get(PATH_MARKER)
        virtual_path = (
            doc_to_virtual_path(
                doc_id=doc_id, title=title, folder_id=folder_id, index=index
            )
            if title_is_explicit
            else virtual_path_of(
                metadata=metadata,
                doc_id=doc_id,
                title=title,
                folder_id=folder_id,
                index=index,
            )
        )
        filename = virtual_path.rsplit("/", 1)[-1]
        stale = _stale_store_path(previous, virtual_path)
        revision = await record_markdown_files(
            workspace_id=workspace_id,
            files={to_store_path(virtual_path): markdown},
            message=f"docs: save {filename}",
            author_user_id=author_user_id,
            removes=[stale] if stale else (),
        )
        if revision is not None and document is not None and previous != virtual_path:
            document.document_metadata = {
                **(document.document_metadata or {}),
                PATH_MARKER: virtual_path,
            }
            # Safe to commit here: the recorder runs at the point of
            # durability, after the save's own commit, so nothing else is
            # pending on this session.
            await session.commit()
    except Exception as exc:
        logger.warning(
            "Knowledge store recording failed for document %s in workspace %s",
            doc_id,
            workspace_id,
            exc_info=True,
        )
        metrics.record_knowledge_store_record_outcome(
            flow="editor_save",
            status="failed",
            error_category=metrics.categorize_exception(exc),
        )
        return None
    metrics.record_knowledge_store_record_outcome(
        flow="editor_save", status="recorded" if revision else "noop"
    )
    return revision


async def record_prepared_documents(
    session: AsyncSession, documents: Sequence[Document]
) -> str | None:
    """Record a sync batch's accepted markdown as one revision.

    Called after ``prepare_for_indexing`` commits — the moment content becomes
    durable — so chunking/embedding failures can never block the record.
    Never raises, for the same coexistence reason as ``record_saved_document``.
    """
    if not documents:
        return None
    workspace_id = documents[0].workspace_id
    if not await knowledge_store_enabled_for(workspace_id):
        return None
    try:
        index = await build_path_index(session, workspace_id)
        files: dict[str, str] = {}
        for doc in documents:
            if not doc.source_markdown:
                continue
            virtual_path = doc_to_virtual_path(
                doc_id=doc.id, title=doc.title, folder_id=doc.folder_id, index=index
            )
            files[to_store_path(virtual_path)] = doc.source_markdown
        revision = await record_markdown_files(
            workspace_id=workspace_id,
            files=files,
            message=f"sync: index {len(files)} document(s)",
            author_user_id=(
                str(documents[0].created_by_id)
                if documents[0].created_by_id is not None
                else None
            ),
        )
    except Exception as exc:
        logger.warning(
            "Knowledge store recording failed for a sync batch in workspace %s",
            workspace_id,
            exc_info=True,
        )
        metrics.record_knowledge_store_record_outcome(
            flow="sync_batch",
            status="failed",
            error_category=metrics.categorize_exception(exc),
        )
        return None
    metrics.record_knowledge_store_record_outcome(
        flow="sync_batch", status="recorded" if revision else "noop"
    )
    return revision


async def record_deleted_documents(
    session: AsyncSession,
    documents: Sequence[Document],
    *,
    author_user_id: str | None = None,
) -> str | None:
    """Drop the files behind ``documents`` in one revision.

    Call this *before* the rows go. A path is read off its row, and a row that
    has been deleted can no longer say where its file was.

    Recording ahead of the delete is safe in this direction only: if the row
    delete then fails, the indexer's own convergence deletes the row, which is
    where the caller was headed anyway. The other order is the bug this verb
    exists for — the file outlives the row, and the next whole-tree rebuild
    reads it back as a document nobody asked for.

    Never raises, for the same coexistence reason as the other verbs.
    """
    if not documents:
        return None
    workspace_id = documents[0].workspace_id
    if not await knowledge_store_enabled_for(workspace_id):
        return None
    try:
        index = await build_path_index(session, workspace_id)
        removes = [
            path
            for path in (_store_path_of(document, index) for document in documents)
            if path is not None
        ]
        revision = await record_markdown_files(
            workspace_id=workspace_id,
            files={},
            message=_summary("delete", removes),
            author_user_id=author_user_id,
            removes=removes,
        )
    except Exception as exc:
        logger.warning(
            "Knowledge store recording failed for a delete in workspace %s",
            workspace_id,
            exc_info=True,
        )
        metrics.record_knowledge_store_record_outcome(
            flow="delete",
            status="failed",
            error_category=metrics.categorize_exception(exc),
        )
        return None
    metrics.record_knowledge_store_record_outcome(
        flow="delete", status="recorded" if revision else "noop"
    )
    return revision


async def record_moved_documents(
    session: AsyncSession,
    documents: Sequence[Document],
    *,
    author_user_id: str | None = None,
) -> str | None:
    """Move each document's file to the path its row now describes.

    Call after the rows carry their new title or folder and before the caller
    commits: the marker still holds where the file is, the row already holds
    where it belongs. One verb covers a document move, a bulk move, a folder
    rename and a folder move — a folder is only a path prefix, so renaming one
    moves every descendant.

    Recorded as a move rather than a delete plus a write so the document keeps
    its id: Phase 4 recognises a renamed file by asking dulwich to detect the
    rename, and an id that churns takes saved citations and version history with
    it.

    Updates the marker on each row it moved, leaving it for the caller's commit
    — unlike :func:`record_saved_document`, which runs after its caller has
    already committed and so has to commit the marker itself.
    """
    if not documents:
        return None
    workspace_id = documents[0].workspace_id
    if not await knowledge_store_enabled_for(workspace_id):
        return None
    try:
        index = await build_path_index(session, workspace_id)
        moves: list[tuple[str, str]] = []
        moved: list[tuple[Document, str]] = []
        for document in documents:
            relocation = _relocation_of(document, index)
            if relocation is None:
                continue
            source, destination, virtual_path = relocation
            moves.append((source, destination))
            moved.append((document, virtual_path))
        revision = await record_markdown_files(
            workspace_id=workspace_id,
            files={},
            message=_summary("move", [destination for _, destination in moves]),
            author_user_id=author_user_id,
            moves=moves,
        )
        if revision is not None:
            for document, virtual_path in moved:
                document.document_metadata = {
                    **(document.document_metadata or {}),
                    PATH_MARKER: virtual_path,
                }
    except Exception as exc:
        logger.warning(
            "Knowledge store recording failed for a move in workspace %s",
            workspace_id,
            exc_info=True,
        )
        metrics.record_knowledge_store_record_outcome(
            flow="move",
            status="failed",
            error_category=metrics.categorize_exception(exc),
        )
        return None
    metrics.record_knowledge_store_record_outcome(
        flow="move", status="recorded" if revision else "noop"
    )
    return revision


def _store_path_of(document: Document, index: PathIndex) -> str | None:
    """Where a row's file lives, or ``None`` when it is not the store's to touch."""
    virtual_path = virtual_path_of(
        metadata=document.document_metadata,
        doc_id=document.id,
        title=document.title,
        folder_id=document.folder_id,
        index=index,
    )
    try:
        return to_store_path(virtual_path)
    except ValueError:
        return None


def _relocation_of(document: Document, index: PathIndex) -> tuple[str, str, str] | None:
    """``(from, to, new virtual path)`` for a row that moved, else ``None``.

    A row with no marker has no file yet — nothing to move, and the next save
    writes it where the row now says.
    """
    previous = (document.document_metadata or {}).get(PATH_MARKER)
    if not isinstance(previous, str):
        return None
    current = doc_to_virtual_path(
        doc_id=document.id,
        title=document.title,
        folder_id=document.folder_id,
        index=index,
    )
    if current == previous:
        return None
    try:
        return to_store_path(previous), to_store_path(current), current
    except ValueError:
        return None


def _summary(verb: str, paths: Sequence[str]) -> str:
    """Commit subject, naming the file when the revision touches only one."""
    if len(paths) == 1:
        return f"docs: {verb} {paths[0].rsplit('/', 1)[-1]}"
    return f"docs: {verb} {len(paths)} documents"


def _stale_store_path(previous: str | None, current: str) -> str | None:
    """Store path the document is moving away from, if it is moving at all."""
    if not previous or previous == current:
        return None
    try:
        return to_store_path(previous)
    except ValueError:
        # A marker from outside the /documents namespace is not ours to drop.
        return None
