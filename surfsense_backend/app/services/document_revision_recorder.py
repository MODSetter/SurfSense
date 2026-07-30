"""Direct-caller adapter: document content changes become knowledge-store revisions.

Editor saves, upload-extracted markdown, and connector sync batches share this
path — the same single write path agent turns use — behind the per-workspace
knowledge-store flag.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    PATH_MARKER,
    build_path_index,
    doc_to_virtual_path,
    to_store_path,
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
) -> str | None:
    """Record ``files`` (store path → markdown) as one revision.

    ``removes`` drops paths in the same revision as the writes — otherwise a
    retitle would leave one document behind as two files.

    ``None`` when the store is disabled, the batch is empty, or nothing
    actually changed (identical content is a no-op by construction).
    """
    if (not files and not removes) or not load_knowledge_store_settings().enabled:
        return None
    store = KnowledgeStore.for_workspace(workspace_id)
    async with store.transaction(
        message=message, author=user_identity(author_user_id)
    ) as tx:
        for path, markdown in files.items():
            tx.write(path, markdown.encode())
        for path in removes:
            tx.remove(path)
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
) -> str | None:
    """Resolve one document's canonical store path and record the save.

    The recorded path is remembered on the row (``document_metadata``), so the
    next save knows where the document used to live and can drop that file
    when a retitle moves it. The marker is written only when a revision was
    actually recorded: a marker without a file would make the row look
    indexer-owned and a later rebuild would prune it.

    Never raises: while the store coexists with the Postgres write path
    (until the Phase 5 cut), a recording failure must not fail the save
    that already committed — it is logged instead.
    """
    if not await knowledge_store_enabled_for(workspace_id):
        return None
    try:
        index = await build_path_index(session, workspace_id)
        virtual_path = doc_to_virtual_path(
            doc_id=doc_id, title=title, folder_id=folder_id, index=index
        )
        document = await session.get(Document, doc_id)
        previous = (
            (document.document_metadata or {}).get(PATH_MARKER) if document else None
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


def _stale_store_path(previous: str | None, current: str) -> str | None:
    """Store path the document is moving away from, if it is moving at all."""
    if not previous or previous == current:
        return None
    try:
        return to_store_path(previous)
    except ValueError:
        # A marker from outside the /documents namespace is not ours to drop.
        return None
