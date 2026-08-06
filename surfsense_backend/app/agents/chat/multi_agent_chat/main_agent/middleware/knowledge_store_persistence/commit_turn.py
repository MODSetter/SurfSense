"""End-of-turn commit body: the turn's working copy becomes one revision.

A free function (not a middleware method) so the stream-task disconnect
fallback can run the identical routine when ``aafter_agent`` is skipped.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.callbacks import dispatch_custom_event

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_message import (
    generate_commit_message,
)
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
    Receipt,
    make_receipt,
)
from app.db import DocumentType
from app.knowledge_store import KnowledgeStore, Outcome
from app.knowledge_store.service import thread_working_copy_id

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

    async def describe(writes, removes) -> str:
        subject = await generate_commit_message(llm, writes=writes, removes=removes)
        return f"{subject}\n\nThread: {thread_id}"

    try:
        outcome = await store.commit_turn(
            thread_id=thread_id, author_user_id=created_by_id, describe=describe
        )
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning(
            "End-of-turn commit failed for workspace %s thread %s: %s",
            workspace_id,
            thread_id,
            exc,
        )
        return {"receipts": await _failed_receipts(store, thread_id, exc)}

    if outcome.revision is None:
        return None
    _announce(outcome, workspace_id=workspace_id, created_by_id=created_by_id)
    return {"receipts": _recorded_receipts(outcome)}


def _announce(
    outcome: Outcome, *, workspace_id: int | str, created_by_id: str | None
) -> None:
    """Tell the still-open chat stream about rows the UI can show right now.

    Without this the sidebar waits for Zero to replicate a row the indexer has
    not written yet. A failed dispatch only costs that head start, so it is
    logged and dropped rather than raised into a turn whose work is committed.
    """
    if outcome.projection is None:
        return
    for event, bucket in _EVENT_BY_BUCKET:
        for document in getattr(outcome.projection, bucket):
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


def _recorded_receipts(outcome: Outcome) -> list[Receipt]:
    """Ground truth for the orchestrator: one receipt per recorded change."""
    return [
        make_receipt(
            route="knowledge_base",
            type="file",
            operation=_OPERATION_BY_KIND[change.kind],
            status="success",
            external_id=outcome.revision,
            preview=change.path,
        )
        for change in outcome.changes
    ]


async def _failed_receipts(
    store: KnowledgeStore, thread_id: int | str | None, exc: Exception
) -> list[Receipt]:
    """One failed receipt per leftover change, read back off the kept copy."""
    try:
        writes, removes = await store.diff_working_copy(thread_working_copy_id(thread_id))
    except FileNotFoundError:
        writes, removes = {}, []
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
