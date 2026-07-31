"""End-of-turn commit body: the turn's working copy becomes one revision.

A free function (not a middleware method) so the stream-task disconnect
fallback can run the identical routine when ``aafter_agent`` is skipped.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from langchain_core.callbacks import dispatch_custom_event

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_message import (
    generate_commit_message,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.git_tree import (
    thread_working_copy_id,
)
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
    Receipt,
    make_receipt,
)
from app.db import DocumentType, shielded_async_session
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import AGENT_IDENTITY, user_identity
from app.knowledge_store.index.project import Projection, project_revision
from app.knowledge_store.index.queue import enqueue_index
from app.observability import metrics

logger = logging.getLogger(__name__)

_OPERATION_BY_KIND = {
    "added": "write_file",
    "modified": "edit_file",
    "removed": "rm",
    "renamed": "move_file",
}

_EVENT_BY_BUCKET = (
    ("document_created", "created"),
    ("document_updated", "updated"),
    ("document_deleted", "deleted"),
)


async def commit_turn_working_copy(
    *,
    workspace_id: int | str,
    thread_id: int | str | None,
    created_by_id: str | None,
    llm: Any,
) -> dict[str, Any] | None:
    """Record the thread's working copy as one revision; return the state delta.

    No copy or an empty diff records nothing. On commit failure the copy is
    kept — the thread's next turn commits the leftover work (recovery) — and
    failed receipts are returned instead of raising, so the turn still ends.
    """
    store = KnowledgeStore.for_workspace(workspace_id)
    copy_id = thread_working_copy_id(thread_id)
    try:
        writes, removes = await store.diff_working_copy(copy_id)
    except FileNotFoundError:
        return None
    if not writes and not removes:
        await store.discard_working_copy(copy_id)
        return None

    subject = await generate_commit_message(llm, writes=writes, removes=removes)
    message = f"{subject}\n\nThread: {thread_id}"
    try:
        async with store.transaction(
            message=message,
            author=user_identity(created_by_id),
            committer=AGENT_IDENTITY,
        ) as tx:
            for path, content in writes.items():
                tx.write(path, content)
            for path in removes:
                tx.remove(path)
    except Exception as exc:
        logger.warning(
            "End-of-turn commit failed for workspace %s thread %s: %s",
            workspace_id,
            thread_id,
            exc,
        )
        metrics.record_knowledge_store_record_outcome(
            flow="turn_commit",
            status="failed",
            error_category=metrics.categorize_exception(exc),
        )
        return {"receipts": _failed_receipts(writes, removes, exc)}

    await store.discard_working_copy(copy_id)
    metrics.record_knowledge_store_record_outcome(
        flow="turn_commit", status="recorded" if tx.revision else "noop"
    )
    if tx.revision is None:
        return None
    # Rows first, then the announcement that names them, then the slow half.
    async with shielded_async_session() as session:
        projection = await project_revision(session, workspace_id, tx.revision)
    _announce(projection, workspace_id=workspace_id, created_by_id=created_by_id)
    enqueue_index(workspace_id)
    return {"receipts": await _recorded_receipts(store, tx.revision)}


def _announce(
    projection: Projection, *, workspace_id: int | str, created_by_id: str | None
) -> None:
    """Tell the still-open chat stream about rows the UI can show right now.

    Without this the sidebar waits for Zero to replicate a row the indexer has
    not written yet. A failed dispatch only costs that head start, so it is
    logged and dropped rather than raised into a turn whose work is committed.
    """
    for event, bucket in _EVENT_BY_BUCKET:
        for document in getattr(projection, bucket):
            try:
                dispatch_custom_event(
                    event,
                    {
                        "id": document.id,
                        "title": document.title,
                        "documentType": DocumentType.NOTE.value,
                        "workspaceId": workspace_id,
                        "folderId": document.folder_id,
                        "createdById": str(created_by_id) if created_by_id else None,
                        "virtualPath": document.virtual_path,
                    },
                )
            except Exception:
                logger.debug("Failed to dispatch %s", event, exc_info=True)


async def _recorded_receipts(store: KnowledgeStore, revision: str) -> list[Receipt]:
    """Ground truth for the orchestrator: one receipt per recorded change."""
    return [
        make_receipt(
            route="knowledge_base",
            type="file",
            operation=_OPERATION_BY_KIND[change.kind],
            status="success",
            external_id=revision,
            preview=change.path,
        )
        for change in await store.list_changes(revision)
    ]


def _failed_receipts(
    writes: Mapping[str, bytes], removes: Iterable[str], exc: Exception
) -> list[Receipt]:
    return [
        make_receipt(
            route="knowledge_base",
            type="file",
            operation="write_file" if is_write else "rm",
            status="failed",
            preview=path,
            error=str(exc),
        )
        for path, is_write in (
            *((p, True) for p in writes),
            *((p, False) for p in removes),
        )
    ]
