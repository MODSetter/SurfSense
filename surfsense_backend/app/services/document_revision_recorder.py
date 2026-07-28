"""Direct-caller adapter: a document save becomes one knowledge-store revision.

Editor saves and upload-extracted markdown share this path — the same single
write path agent turns use — behind ``KNOWLEDGE_STORE_ENABLED``.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    build_path_index,
    doc_to_virtual_path,
)
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.settings import load_knowledge_store_settings

logger = logging.getLogger(__name__)


async def record_document_markdown(
    *,
    workspace_id: int | str,
    store_path: str,
    markdown: str,
    author_user_id: str | None,
) -> str | None:
    """Record one revision for one saved document; ``None`` when disabled."""
    if not load_knowledge_store_settings().enabled:
        return None
    store = KnowledgeStore.for_workspace(workspace_id)
    filename = store_path.rsplit("/", 1)[-1]
    async with store.transaction(
        message=f"docs: save {filename}", author=user_identity(author_user_id)
    ) as tx:
        tx.write(store_path, markdown.encode())
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
        return await record_document_markdown(
            workspace_id=workspace_id,
            store_path=virtual_path.lstrip("/"),
            markdown=markdown,
            author_user_id=author_user_id,
        )
    except Exception:
        logger.warning(
            "Knowledge store recording failed for document %s in workspace %s",
            doc_id,
            workspace_id,
            exc_info=True,
        )
        return None
