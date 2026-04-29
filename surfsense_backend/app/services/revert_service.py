"""Revert service for the SurfSense agent action log.

Implements the actual revert workflow used by
``POST /api/threads/{thread_id}/revert/{action_id}``. The route handler is a
thin auth + flag wrapper around the functions defined here.

Operation outcomes mirror the plan:

* **KB-owned actions** (NOTE / FILE / FOLDER mutations): restore from
  :class:`app.db.DocumentRevision` / :class:`app.db.FolderRevision` rows
  written before the original mutation.
* **Connector-owned actions with a declared ``reverse_descriptor``**: invoke
  the inverse tool through the agent's normal permission stack (NOT
  bypassed). Out of scope for this PR — returns ``REVERSE_NOT_IMPLEMENTED``.
* **Anything else** (deprecated tool / no descriptor / schema drift):
  returns ``NOT_REVERSIBLE`` and the route surfaces it as 409.

A successful revert appends a NEW row to ``agent_action_log`` with
``reverse_of=<original_action_id>`` and the requesting user's
``user_id``, preserving an auditable chain.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    AgentActionLog,
    DocumentRevision,
    FolderRevision,
    NewChatThread,
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
# Revert paths
# ---------------------------------------------------------------------------


async def _restore_document_revision(
    session: AsyncSession, *, action: AgentActionLog
) -> RevertOutcome:
    """Restore the most recent :class:`DocumentRevision` for ``action``."""
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

    from app.db import Document  # late import to avoid cycles at module load

    doc = await session.get(Document, revision.document_id)
    if doc is None:
        return RevertOutcome(
            status="tool_unavailable",
            message="Original document has been deleted; revert cannot proceed.",
        )

    if revision.content_before is not None:
        doc.content = revision.content_before
    if revision.title_before is not None:
        doc.title = revision.title_before
    if revision.folder_id_before is not None:
        doc.folder_id = revision.folder_id_before
    doc.updated_at = datetime.now(UTC)
    return RevertOutcome(status="ok", message="Document restored from snapshot.")


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

    from app.db import Folder

    folder = await session.get(Folder, revision.folder_id)
    if folder is None:
        return RevertOutcome(
            status="tool_unavailable",
            message="Original folder has been deleted; revert cannot proceed.",
        )

    if revision.name_before is not None:
        folder.name = revision.name_before
    if revision.parent_id_before is not None:
        folder.parent_id = revision.parent_id_before
    if revision.position_before is not None:
        folder.position = revision.position_before
    folder.updated_at = datetime.now(UTC)
    return RevertOutcome(status="ok", message="Folder restored from snapshot.")


# Tool-name prefixes that route to KB document / folder revert paths. Kept
# as data so a future PR adding new KB-owned tools doesn't have to touch
# this module's control flow.
_DOC_TOOL_PREFIXES: tuple[str, ...] = (
    "edit_file",
    "write_file",
    "update_memory",
    "create_note",
    "update_note",
    "delete_note",
)
_FOLDER_TOOL_PREFIXES: tuple[str, ...] = (
    "mkdir",
    "move_file",
    "rename_folder",
    "delete_folder",
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

    if tool_name.startswith(_DOC_TOOL_PREFIXES):
        outcome = await _restore_document_revision(session, action=action)
    elif tool_name.startswith(_FOLDER_TOOL_PREFIXES):
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
