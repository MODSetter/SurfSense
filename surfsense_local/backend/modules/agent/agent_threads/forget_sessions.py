"""Deleting a thread's or a workspace's agent sessions along with their rows.

Best effort: opencode runs only once a turn has needed it in this run of the
app, and a deletion must not fail because it is not running.
"""

import logging
from collections.abc import Sequence

import httpx
from anyio import from_thread
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.chat.models import ChatThread
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


async def forget_sessions(workspace_id: int, session_ids: Sequence[str]) -> None:
    """Stop the sessions' turns, then delete the sessions."""
    if not session_ids:
        return
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return
    folder = get_storage_settings().agent_working_dir(workspace_id)
    async with client:
        for session_id in session_ids:
            try:
                await client.abort(folder, session_id)
                await client.delete_session(folder, session_id)
            except httpx.HTTPError:
                logger.warning(
                    "agent session %s was not deleted", session_id, exc_info=True
                )


def forget_workspace_sessions(session: Session, workspace_id: int) -> None:
    """The workspace's agent sessions, deleted before the workspace is.

    Called from the workspace route, which runs in a worker thread.
    """
    session_ids = session.scalars(
        select(ChatThread.opencode_session_id).where(
            ChatThread.workspace_id == workspace_id,
            ChatThread.opencode_session_id.is_not(None),
        )
    ).all()
    if session_ids:
        from_thread.run(forget_sessions, workspace_id, [s for s in session_ids if s])
