"""A step of an agent thread as opencode stored it, whole: the turn's frames carry only the start of its result."""

from typing import Any

import httpx
from fastapi import HTTPException, status

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.chat.models import ChatThread
from shared.config import get_storage_settings


async def stored_step(thread: ChatThread, part_id: str) -> dict[str, Any]:
    """The tool part `part_id` of the thread's session.

    A thread on screen has started opencode already, so this needs no new configuration.
    """
    if thread.opencode_session_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    try:
        client = connect_opencode()
    except AgentUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    folder = get_storage_settings().thread_working_dir(thread.workspace_id, thread.id)
    async with client:
        try:
            messages = await client.messages(folder, thread.opencode_session_id)
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
            ) from error
    for message in messages:
        for part in message.get("parts", []):
            if part.get("id") == part_id and part.get("type") == "tool":
                return part
    raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step in this thread")
