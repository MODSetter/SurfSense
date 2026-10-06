"""Deleting a thread's or a workspace's agent sessions, and freeing their opencode instances.

Best effort: opencode runs only once a turn has needed it in this run of the
app, and a deletion must not fail because it is not running.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

import httpx
from anyio import from_thread
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.agent_threads.legacy_thread import forget_legacy, is_legacy
from modules.agent.agent_threads.live_instances import forget_instance
from modules.agent.opencode_client import OpencodeClient
from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.agent.thread_folder.layout import forget_thread_lock
from modules.chat.models import ChatThread
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


async def forget_thread(workspace_id: int, thread_id: int, session_id: str) -> Path:
    """Stop and delete the thread's session and free its instance.

    Returns the thread's folder, for the caller to remove once the row is gone.
    """
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return folder
    async with client:
        await _forget(client, folder, session_id)
    return folder


async def forget_threads(workspace_id: int, threads: Sequence[tuple[int, str]]) -> None:
    """Every agent thread of a workspace about to be deleted, by id and session."""
    if not threads:
        return
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return
    storage = get_storage_settings()
    folders = [storage.thread_working_dir(workspace_id, t) for t, _ in threads]
    async with client:
        legacy = [
            await _forget(client, folder, session_id)
            for folder, (_, session_id) in zip(folders, threads, strict=True)
        ]
        if any(legacy):
            await _dispose(client, storage.agent_working_dir(workspace_id))
    for folder in folders:
        forget_thread_lock(folder)


def forget_workspace_sessions(session: Session, workspace_id: int) -> None:
    """The workspace's agent threads, forgotten before the workspace is deleted.

    Called from the workspace route, which runs in a worker thread.
    """
    threads = session.execute(
        select(ChatThread.id, ChatThread.opencode_session_id).where(
            ChatThread.workspace_id == workspace_id,
            ChatThread.opencode_session_id.is_not(None),
        )
    ).all()
    if threads:
        from_thread.run(
            forget_threads,
            workspace_id,
            [(t.id, t.opencode_session_id) for t in threads],
        )


async def _forget(client: OpencodeClient, folder: Path, session_id: str) -> bool:
    """Abort and delete the session, then dispose the folder's instance; whether it was legacy.

    A legacy session's instance is the one every legacy thread of the workspace shares.
    """
    try:
        legacy = await is_legacy(client, session_id, folder)
    except httpx.HTTPError:
        legacy = False  # gone from opencode already: the folder is the thread's own
    try:
        await client.abort(folder, session_id)
        await client.delete_session(folder, session_id)
    except httpx.HTTPError:
        logger.warning("agent session %s was not deleted", session_id, exc_info=True)
    if not legacy:
        await _dispose(client, folder)
    forget_instance(folder)
    forget_legacy(session_id)
    return legacy


async def _dispose(client: OpencodeClient, folder: Path) -> None:
    try:
        await client.dispose_instance(folder)
    except httpx.HTTPError:
        logger.warning("opencode kept the instance of %s", folder, exc_info=True)
