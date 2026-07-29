"""Direct-caller adapter: a document save becomes one knowledge-store revision.

Editor saves and upload-extracted markdown share this path — the same single
write path agent turns use — behind ``KNOWLEDGE_STORE_ENABLED``.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
    to_store_path,
)
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.index_queue import enqueue_index
from app.knowledge_store.settings import load_knowledge_store_settings

logger = logging.getLogger(__name__)


async def record_document_markdown(
    *,
    workspace_id: int | str,
    store_path: str,
    markdown: str,
    author_user_id: str | None,
    stale_store_path: str | None = None,
) -> str | None:
    """Record one revision for one saved document; ``None`` when disabled.

    ``stale_store_path`` is the document's previous location, dropped in the same
    revision as the write. Without it a retitled document leaves its old file
    behind and one document becomes two files.
    """
    if not load_knowledge_store_settings().enabled:
        return None
    store = KnowledgeStore.for_workspace(workspace_id)
    filename = store_path.rsplit("/", 1)[-1]
    async with store.transaction(
        message=f"docs: save {filename}", author=user_identity(author_user_id)
    ) as tx:
        if stale_store_path and stale_store_path != store_path:
            tx.remove(stale_store_path)
        tx.write(store_path, markdown.encode())
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
    """Resolve the document's canonical store path and record the save.

    The resolved path is remembered on the row (``document_metadata``), so the
    next save knows where the document used to live and can drop that file when
    a retitle moves it.

    Never raises: while the store coexists with the Postgres write path
    (until the Phase 5 cut), a recording failure must not fail the save
    that already committed — it is logged instead.
    """
    if not load_knowledge_store_settings().enabled:
        return None
    try:
        index = await build_path_index(session, workspace_id)
        virtual_path = doc_to_virtual_path(
            doc_id=doc_id, title=title, folder_id=folder_id, index=index
        )
        document = await session.get(Document, doc_id)
        previous = (
            (document.document_metadata or {}).get("virtual_path") if document else None
        )
        revision = await record_document_markdown(
            workspace_id=workspace_id,
            store_path=to_store_path(virtual_path),
            markdown=markdown,
            author_user_id=author_user_id,
            stale_store_path=_stale_store_path(previous, virtual_path),
        )
        if document is not None and previous != virtual_path:
            document.document_metadata = {
                **(document.document_metadata or {}),
                "virtual_path": virtual_path,
            }
            await session.commit()
        return revision
    except Exception:
        logger.warning(
            "Knowledge store recording failed for document %s in workspace %s",
            doc_id,
            workspace_id,
            exc_info=True,
        )
        return None


def _stale_store_path(previous: str | None, current: str) -> str | None:
    """Store path the document is moving away from, if it is moving at all."""
    if not previous or previous == current:
        return None
    if not previous.startswith(f"{DOCUMENTS_ROOT}/"):
        return None
    return to_store_path(previous)
