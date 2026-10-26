"""A step of an agent thread as opencode stored it, whole: the turn's frames carry only the start of its result."""

from typing import Any

import httpx
from fastapi import HTTPException, status

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.chat.models import ChatThread


async def stored_step(thread: ChatThread, call_id: str) -> dict[str, Any]:
    """The tool call `call_id` of the thread's session, as opencode stored it.

    A thread on screen has started opencode already, so this needs no new configuration.
    """
    if thread.opencode_session_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    try:
        client = connect_opencode()
    except AgentUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    async with client:
        try:
            messages = await client.messages(thread.opencode_session_id)
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
            ) from error
    for message in messages:
        for item in message.get("content") or []:
            if item.get("id") == call_id and item.get("type") == "tool":
                return item
    raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step in this thread")
