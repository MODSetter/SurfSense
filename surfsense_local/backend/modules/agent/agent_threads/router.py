from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.chat.dependencies import ThreadDep
from shared.config import get_storage_settings

router = APIRouter(tags=["agent"])


class PermissionReply(BaseModel):
    """The user's answer: allow this one time, or refuse. There is no "always" (ADR 0028)."""

    reply: Literal["once", "reject"]


@router.post(
    "/chat/threads/{thread_id}/permissions/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Answer the agent's request to run something",
)
async def answer_permission(
    thread: ThreadDep, request_id: str, payload: PermissionReply
) -> Response:
    """Pass the user's answer to the opencode session waiting on it."""
    if not thread.uses_agent:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    try:
        client = connect_opencode()
    except AgentUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    folder = get_storage_settings().thread_working_dir(thread.workspace_id, thread.id)
    async with client:
        try:
            await client.reply(folder, request_id, payload.reply)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, "no such request is waiting"
                ) from error
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"opencode refused the answer: {error}"
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
            ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
