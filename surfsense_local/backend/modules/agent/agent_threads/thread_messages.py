from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.agent.agent_threads.replies import thread_turns
from modules.agent.opencode_client import OpencodeVersionError
from modules.agent.opencode_runtime import AgentUnavailableError, ready_opencode
from modules.chat.models import ChatThread
from modules.llm.resolution import ModelResolutionError
from shared.config import get_storage_settings


async def agent_thread_messages(
    session: Session, thread: ChatThread, launch_key: str
) -> list[dict[str, Any]]:
    """An agent thread's turns, read from the opencode session that holds them.

    opencode may not be running yet in this run of the app, so reading starts it.
    """
    session_id = thread.opencode_session_id
    if session_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    try:
        ready = await ready_opencode(session, launch_key=launch_key)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (AgentUnavailableError, OpencodeVersionError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    folder = get_storage_settings().agent_working_dir(thread.workspace_id)
    try:
        return thread_turns(await ready.client.messages(folder, session_id))
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
        ) from error
    finally:
        await ready.client.close()
