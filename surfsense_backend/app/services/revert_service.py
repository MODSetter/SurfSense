"""Revert service for the SurfSense agent action log.

Implements the actual revert workflow used by
``POST /api/threads/{thread_id}/revert/{action_id}``. The route handler is a
thin auth + flag wrapper around the functions defined here.

Operation outcomes mirror the plan:

* **KB-owned actions** (NOTE / FILE / FOLDER mutations): restore from
  :class:`app.db.DocumentRevision` / :class:`app.db.FolderRevision` rows
  written before the original mutation. ``rm``/``rmdir`` re-INSERT a fresh
  row from the snapshot; ``write_file`` create / ``mkdir`` DELETE the row
  that was created; everything else is an in-place restore.
* **Connector-owned actions with a declared ``reverse_descriptor``**: invoke
  the inverse tool through the agent's normal permission stack (NOT
  bypassed). Out of scope for this PR — returns ``REVERSE_NOT_IMPLEMENTED``.
* **Anything else** (deprecated tool / no descriptor / schema drift):
  returns ``NOT_REVERSIBLE`` and the route surfaces it as 409.

A successful revert appends a NEW row to ``agent_action_log`` with
``reverse_of=<original_action_id>`` and the requesting user's
``user_id``, preserving an auditable chain.

Dispatch must be exact-match (``tool_name == name``), NOT prefix matching.
``"rmdir".startswith("rm")`` would otherwise mis-route directory revert
to the document branch (and ``delete_note`` vs ``delete_folder`` is the
same trap waiting to happen).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.path_resolver import (
    DOCUMENTS_ROOT,
    safe_filename,
    safe_folder_segment,
)
from app.db import (
    AgentActionLog,
    Chunk,
    Document,
    DocumentRevision,
    DocumentType,
    Folder,
    FolderRevision,
    NewChatThread,
)
from app.utils.document_converters import (
    embed_texts,
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


RevertOutcomeStatus = Literal[
    "ok",
    "not_reversible",
    "not_found",
    "permission_denied",
    "tool_unavailable",
    "reverse_not_implemented",
]


@dataclass
class RevertOutcome:
    """Structured result of :func:`revert_action`."""

    status: RevertOutcomeStatus
    message: str
    new_action_id: int | None = None


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def load_action(
    session: AsyncSession,
    *,
    action_id: int,
    thread_id: int,
) -> AgentActionLog | None:
    """Load the action_log row for ``action_id`` if it belongs to the thread."""
    stmt = select(AgentActionLog).where(
        AgentActionLog.id == action_id,
        AgentActionLog.thread_id == thread_id,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def load_thread(session: AsyncSession, *, thread_id: int) -> NewChatThread | None:
    stmt = select(NewChatThread).where(NewChatThread.id == thread_id)
    result = await session.execute(stmt)
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def can_revert(
    *,
    requester_user_id: str | None,
    action: AgentActionLog,
    is_admin: bool,
) -> bool:
    """Return True iff the requester is allowed to revert this action.

    The plan's rule: "requester must be the original `user_id` on the
    action, or hold the search-space admin role." Anonymous actions
    (``action.user_id is None``) can only be reverted by admins.
    """
    if is_admin:
        return True
    if action.user_id is None:
        return False
    return str(action.user_id) == str(requester_user_id)


# ---------------------------------------------------------------------------
# Helper: reconstruct virtual path from a snapshot
# ---------------------------------------------------------------------------


async def _virtual_path_from_snapshot(
    session: AsyncSession,
    revision: DocumentRevision,
) -> str | None:
    """Reconstruct the virtual_path the document was at before mutation.

    Preference order:
    1. ``metadata_before["virtual_path"]`` — written by every snapshot
       helper since this PR.
    2. Compose ``"<folder_path>/<title_before>"`` from
       ``folder_id_before`` + ``title_before``. Walks the folder chain via
       ``parent_id``.
    """
    metadata = revision.metadata_before or {}
    candidate = metadata.get("virtual_path") if isinstance(metadata, dict) else None
    if isinstance(candidate, str) and candidate.startswith(DOCUMENTS_ROOT):
        return candidate

    title = revision.title_before
    if not isinstance(title, str) or not title:
        return None

    parts: list[str] = []
    cursor: int | None = revision.folder_id_before
    visited: set[int] = set()
    while cursor is not None and cursor not in visited:
        visited.add(cursor)
        folder = await session.get(Folder, cursor)
        if folder is None:
            return None
        parts.append(safe_folder_segment(str(folder.name or "")))
        cursor = folder.parent_id
    parts.reverse()

    base = f"{DOCUMENTS_ROOT}/" + "/".join(parts) if parts else DOCUMENTS_ROOT
    filename = safe_filename(title)
    return f"{base}/{filename}"


# ---------------------------------------------------------------------------
# Document revision restore (write/edit/move/rm)
# ---------------------------------------------------------------------------


def _set_field(target: Any, field: str, value: Any) -> None:
    if value is not None:
        setattr(target, field, value)


async def _restore_in_place_document(
    session: AsyncSession,
    *,
    revision: DocumentRevision,
) -> RevertOutcome:
    """Apply an in-place restore to an existing :class:`Document`."""
    if revision.document_id is None:
        return RevertOutcome(
            status="tool_unavailable",
            message=(
                "Original document was hard-deleted; in-place restore is not possible."
            ),
        )
    doc = await session.get(Document, revision.document_id)
    if doc is None:
        return RevertOutcome(
            status="tool_unavailable",
            message="Original document has been deleted; revert cannot proceed.",
        )

    _set_field(doc, "content", revision.content_before)
    _set_field(doc, "source_markdown", revision.content_before)
    _set_field(doc, "title", revision.title_before)
    _set_field(doc, "folder_id", revision.folder_id_before)
    metadata_before = revision.metadata_before or {}
    if isinstance(metadata_before, dict) and metadata_before:
        doc.document_metadata = dict(metadata_before)

    if isinstance(revision.content_before, str):
        doc.content_hash = generate_content_hash(
            revision.content_before, doc.search_space_id
        )

    virtual_path = await _virtual_path_from_snapshot(session, revision)
    if virtual_path:
        doc.unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.NOTE,
            virtual_path,
            doc.search_space_id,
        )

    chunks_before = revision.chunks_before
    if isinstance(chunks_before, list):
        await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        chunk_texts = [
            str(c.get("content"))
            for c in chunks_before
            if isinstance(c, dict) and isinstance(c.get("content"), str)
        ]
        if chunk_texts:
            chunk_embeddings = embed_texts(chunk_texts)
            session.add_all(
                [
                    Chunk(document_id=doc.id, content=text, embedding=embedding)
                    for text, embedding in zip(
                        chunk_texts, chunk_embeddings, strict=True
                    )
                ]
            )
            if isinstance(revision.content_before, str):
                doc.embedding = embed_texts([revision.content_before])[0]

    doc.updated_at = datetime.now(UTC)
    return RevertOutcome(status="ok", message="Document restored from snapshot.")


async def _reinsert_document_from_revision(
    session: AsyncSession,
    *,
    revision: DocumentRevision,
) -> RevertOutcome:
    """Re-INSERT a deleted :class:`Document` from a snapshot row (``rm`` revert)."""
    if not isinstance(revision.title_before, str) or not revision.title_before:
        return RevertOutcome(
            status="not_reversible",
            message="Snapshot lacks title_before; cannot recreate document.",
        )
    if not isinstance(revision.content_before, str):
        return RevertOutcome(
            status="not_reversible",
            message="Snapshot lacks content_before; cannot recreate document.",
        )

    virtual_path = await _virtual_path_from_snapshot(session, revision)
    if not virtual_path:
        return RevertOutcome(
            status="not_reversible",
            message=(
                "Snapshot is missing both metadata_before['virtual_path'] AND "
                "a resolvable (folder_id_before, title_before) pair."
            ),
        )

    search_space_id = revision.search_space_id
    unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        virtual_path,
        search_space_id,
    )
    collision = await session.execute(
        select(Document.id).where(
            Document.search_space_id == search_space_id,
            Document.unique_identifier_hash == unique_identifier_hash,
        )
    )
    if collision.scalar_one_or_none() is not None:
        return RevertOutcome(
            status="tool_unavailable",
            message=(
                f"A document already exists at '{virtual_path}'; revert would "
                "collide. Move the live doc out of the way first."
            ),
        )

    metadata = revision.metadata_before or {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata["virtual_path"] = virtual_path

    content = revision.content_before
    new_doc = Document(
        title=revision.title_before,
        document_type=DocumentType.NOTE,
        document_metadata=metadata,
        content=content,
        content_hash=generate_content_hash(content, search_space_id),
        unique_identifier_hash=unique_identifier_hash,
        source_markdown=content,
        search_space_id=search_space_id,
        folder_id=revision.folder_id_before,
        updated_at=datetime.now(UTC),
    )
    session.add(new_doc)
    await session.flush()

    new_doc.embedding = embed_texts([content])[0]
    chunk_texts = []
    chunks_before = revision.chunks_before
    if isinstance(chunks_before, list):
        chunk_texts = [
            str(c.get("content"))
            for c in chunks_before
            if isinstance(c, dict) and isinstance(c.get("content"), str)
        ]
    if chunk_texts:
        chunk_embeddings = embed_texts(chunk_texts)
        session.add_all(
            [
                Chunk(document_id=new_doc.id, content=text, embedding=embedding)
                for text, embedding in zip(chunk_texts, chunk_embeddings, strict=True)
            ]
        )

    # Repoint the snapshot at the recreated row so a follow-up revert of
    # the same row works as expected.
    revision.document_id = new_doc.id
    return RevertOutcome(
        status="ok",
        message=f"Re-inserted document '{revision.title_before}' from snapshot.",
    )


async def _delete_created_document(
    session: AsyncSession,
    *,
    revision: DocumentRevision,
) -> RevertOutcome:
    """Delete the document that ``write_file`` created (``content_before IS NULL``)."""
    if revision.document_id is None:
        return RevertOutcome(
            status="ok",
            message="No live row to delete (already removed elsewhere).",
        )
    await session.execute(delete(Document).where(Document.id == revision.document_id))
    return RevertOutcome(
        status="ok",
        message="Deleted the document that was created by this action.",
    )


async def _restore_document_revision(
    session: AsyncSession, *, action: AgentActionLog
) -> RevertOutcome:
    """Dispatch document-level revert based on ``action.tool_name``."""
    stmt = (
        select(DocumentRevision)
        .where(DocumentRevision.agent_action_id == action.id)
        .order_by(DocumentRevision.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    revision = result.scalars().first()
    if revision is None:
        return RevertOutcome(
            status="not_reversible",
            message="No document_revisions row tied to this action.",
        )

    tool_name = (action.tool_name or "").lower()

    if tool_name == "rm":
        return await _reinsert_document_from_revision(session, revision=revision)

    if tool_name == "write_file" and revision.content_before is None:
        return await _delete_created_document(session, revision=revision)

    return await _restore_in_place_document(session, revision=revision)


# ---------------------------------------------------------------------------
# Folder revision restore (mkdir/rmdir/rename/move)
# ---------------------------------------------------------------------------


async def _restore_in_place_folder(
    session: AsyncSession,
    *,
    revision: FolderRevision,
) -> RevertOutcome:
    if revision.folder_id is None:
        return RevertOutcome(
            status="tool_unavailable",
            message="Original folder was hard-deleted; in-place restore is impossible.",
        )
    folder = await session.get(Folder, revision.folder_id)
    if folder is None:
        return RevertOutcome(
            status="tool_unavailable",
            message="Original folder has been deleted; revert cannot proceed.",
        )
    _set_field(folder, "name", revision.name_before)
    _set_field(folder, "parent_id", revision.parent_id_before)
    _set_field(folder, "position", revision.position_before)
    folder.updated_at = datetime.now(UTC)
    return RevertOutcome(status="ok", message="Folder restored from snapshot.")


async def _reinsert_folder_from_revision(
    session: AsyncSession,
    *,
    revision: FolderRevision,
) -> RevertOutcome:
    if not isinstance(revision.name_before, str) or not revision.name_before:
        return RevertOutcome(
            status="not_reversible",
            message="Snapshot lacks name_before; cannot recreate folder.",
        )
    new_folder = Folder(
        name=revision.name_before,
        parent_id=revision.parent_id_before,
        position=revision.position_before,
        search_space_id=revision.search_space_id,
        updated_at=datetime.now(UTC),
    )
    session.add(new_folder)
    await session.flush()
    revision.folder_id = new_folder.id
    return RevertOutcome(
        status="ok",
        message=f"Re-inserted folder '{revision.name_before}' from snapshot.",
    )


async def _delete_created_folder(
    session: AsyncSession,
    *,
    revision: FolderRevision,
) -> RevertOutcome:
    if revision.folder_id is None:
        return RevertOutcome(
            status="ok",
            message="No live folder row to delete (already removed elsewhere).",
        )
    folder_id = revision.folder_id

    has_doc = await session.execute(
        select(Document.id).where(Document.folder_id == folder_id).limit(1)
    )
    if has_doc.scalar_one_or_none() is not None:
        return RevertOutcome(
            status="tool_unavailable",
            message=(
                "Folder is no longer empty (documents have been added since "
                "mkdir); cannot revert."
            ),
        )
    has_child = await session.execute(
        select(Folder.id).where(Folder.parent_id == folder_id).limit(1)
    )
    if has_child.scalar_one_or_none() is not None:
        return RevertOutcome(
            status="tool_unavailable",
            message=(
                "Folder is no longer empty (sub-folders have been added "
                "since mkdir); cannot revert."
            ),
        )

    await session.execute(delete(Folder).where(Folder.id == folder_id))
    return RevertOutcome(
        status="ok",
        message="Deleted the folder that was created by this action.",
    )


async def _restore_folder_revision(
    session: AsyncSession, *, action: AgentActionLog
) -> RevertOutcome:
    stmt = (
        select(FolderRevision)
        .where(FolderRevision.agent_action_id == action.id)
        .order_by(FolderRevision.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    revision = result.scalars().first()
    if revision is None:
        return RevertOutcome(
            status="not_reversible",
            message="No folder_revisions row tied to this action.",
        )

    tool_name = (action.tool_name or "").lower()

    if tool_name == "rmdir":
        return await _reinsert_folder_from_revision(session, revision=revision)

    if tool_name == "mkdir":
        return await _delete_created_folder(session, revision=revision)

    return await _restore_in_place_folder(session, revision=revision)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
#
# Exact-name dispatch: ``tool_name == name``, NOT ``startswith(...)``.
# Prefix-matching mis-routes pairs like ``rm``/``rmdir`` and
# ``delete_note``/``delete_folder``.

_DOC_TOOLS: frozenset[str] = frozenset(
    {
        "edit_file",
        "write_file",
        "move_file",
        "rm",
        "update_memory",
        "create_note",
        "update_note",
        "delete_note",
    }
)
_FOLDER_TOOLS: frozenset[str] = frozenset(
    {
        "mkdir",
        "rmdir",
        "rename_folder",
        "delete_folder",
    }
)


async def revert_action(
    session: AsyncSession,
    *,
    action: AgentActionLog,
    requester_user_id: str | None,
) -> RevertOutcome:
    """Execute the revert for ``action`` and return a structured outcome.

    The function does **not** commit — the caller is expected to commit on
    success or roll back on failure. A new ``agent_action_log`` row is
    added to the session on success with ``reverse_of=action.id``.
    """
    tool_name = (action.tool_name or "").lower()

    if tool_name in _DOC_TOOLS:
        outcome = await _restore_document_revision(session, action=action)
    elif tool_name in _FOLDER_TOOLS:
        outcome = await _restore_folder_revision(session, action=action)
    elif action.reverse_descriptor:
        # Connector-owned reversibles run through the normal permission
        # stack; out of scope for this PR — the route returns 503 anyway
        # until UI ships, so 501-style "not implemented" is fine.
        return RevertOutcome(
            status="reverse_not_implemented",
            message=(
                "Connector-action revert is not yet implemented. The "
                "reverse_descriptor is stored; future work will replay it "
                "through PermissionMiddleware."
            ),
        )
    else:
        return RevertOutcome(
            status="not_reversible",
            message=(
                f"Tool {action.tool_name!r} is not reversible: no document "
                "revision and no reverse_descriptor."
            ),
        )

    if outcome.status != "ok":
        return outcome

    new_row = AgentActionLog(
        thread_id=action.thread_id,
        user_id=requester_user_id,
        search_space_id=action.search_space_id,
        turn_id=None,
        message_id=None,
        tool_name=f"_revert:{action.tool_name}",
        args={"reverted_action_id": action.id},
        result_id=None,
        reversible=False,
        reverse_descriptor=None,
        error=None,
        reverse_of=action.id,
    )
    session.add(new_row)
    await session.flush()
    outcome.new_action_id = new_row.id
    return outcome


__all__ = [
    "RevertOutcome",
    "can_revert",
    "load_action",
    "load_thread",
    "revert_action",
]
