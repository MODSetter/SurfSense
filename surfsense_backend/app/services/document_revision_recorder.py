"""Direct-caller adapter: document content changes become knowledge-store revisions.

Editor saves, upload-extracted markdown, and connector sync batches share this
path — the same single write path agent turns use — behind
``KNOWLEDGE_STORE_ENABLED``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import (
    build_path_index,
    doc_to_virtual_path,
)
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)

if TYPE_CHECKING:
    from app.db import Document

logger = logging.getLogger(__name__)


async def record_markdown_files(
    *,
    workspace_id: int | str,
    files: Mapping[str, str],
    message: str,
    author_user_id: str | None,
) -> str | None:
    """Record ``files`` (store path → markdown) as one revision.

    ``None`` when the store is disabled, the batch is empty, or nothing
    actually changed (identical content is a no-op by construction).
    """
    if not files or not load_knowledge_store_settings().enabled:
        return None
    store = KnowledgeStore.for_workspace(workspace_id)
    async with store.transaction(
        message=message, author=user_identity(author_user_id)
    ) as tx:
        for path, markdown in files.items():
            tx.write(path, markdown.encode())
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
        filename = virtual_path.rsplit("/", 1)[-1]
        return await record_markdown_files(
            workspace_id=workspace_id,
            files={virtual_path.lstrip("/"): markdown},
            message=f"docs: save {filename}",
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
            files[virtual_path.lstrip("/")] = doc.source_markdown
        return await record_markdown_files(
            workspace_id=workspace_id,
            files=files,
            message=f"sync: index {len(files)} document(s)",
            author_user_id=(
                str(documents[0].created_by_id)
                if documents[0].created_by_id is not None
                else None
            ),
        )
    except Exception:
        logger.warning(
            "Knowledge store recording failed for a sync batch in workspace %s",
            workspace_id,
            exc_info=True,
        )
        return None
