import logging

import httpx
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from modules.agent.opencode_client import OpencodeVersionError
from modules.agent.opencode_runtime import AgentUnavailableError, ready_opencode
from modules.agent.thread_folder.layout import fresh_thread_folder
from modules.chat.models import ChatThread
from modules.llm.resolution import ModelResolutionError

logger = logging.getLogger(__name__)


async def open_agent_session(
    session: Session, thread: ChatThread, launch_key: str
) -> str | None:
    """Open the opencode session a new thread's turns will live in, in the thread's own folder.

    The folder is filled before each turn, not here.

    None when the agent cannot answer right now, and the thread is then the
    chat's: a thread must open whatever state opencode is in.
    """
    try:
        ready = await ready_opencode(session, launch_key=launch_key)
    except (
        AgentUnavailableError,
        OpencodeVersionError,
        ModelResolutionError,
        httpx.HTTPError,
    ):
        logger.warning(
            "thread %s opens as a chat: the agent is not ready",
            thread.id,
            exc_info=True,
        )
        return None
    try:
        folder = await run_in_threadpool(
            fresh_thread_folder, thread.workspace_id, thread.id
        )
        return await ready.client.create_session(folder, thread.title or "New chat")
    except OSError:
        logger.warning(
            "thread %s opens as a chat: its folder holds a deleted thread's files",
            thread.id,
            exc_info=True,
        )
        return None
    except httpx.HTTPError:
        logger.warning(
            "thread %s opens as a chat: opencode refused the session",
            thread.id,
            exc_info=True,
        )
        return None
    finally:
        await ready.client.close()
