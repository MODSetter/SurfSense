from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from modules.agent.engines.thread_engine import thread_engine
from modules.chat.dependencies import ThreadDep

router = APIRouter(tags=["agent"])


class PermissionReply(BaseModel):
    """The user's answer: allow this one time, or refuse. There is no "always" (ADR 0028)."""

    reply: Literal["once", "reject"]


class StepResult(BaseModel):
    """What a step returned, or why it failed, whole."""

    output: str | None
    error: str | None


@router.get(
    "/chat/threads/{thread_id}/steps/{part_id}/result",
    response_model=StepResult,
    summary="Read the whole result of an agent's step",
)
async def read_step_result(thread: ThreadDep, part_id: str) -> StepResult:
    state = (await thread_engine(thread).stored_step(thread, part_id)).get(
        "state"
    ) or {}
    output, error = state.get("output"), state.get("error")
    return StepResult(
        output=None if output is None else str(output),
        error=None if error is None else str(error),
    )


@router.post(
    "/chat/threads/{thread_id}/permissions/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Answer the agent's request to run something",
)
async def answer_permission(
    thread: ThreadDep, request_id: str, payload: PermissionReply
) -> Response:
    """Pass the user's answer to the engine waiting on it."""
    if not thread.uses_agent:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    await thread_engine(thread).answer_permission(thread, request_id, payload.reply)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
