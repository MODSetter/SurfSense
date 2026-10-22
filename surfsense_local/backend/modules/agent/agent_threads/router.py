from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.agent.agent_threads.steps import tool_output
from modules.agent.engines.both_sessions import stored_step_of
from modules.agent.engines.thread_engine import every_engine, thread_engine
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
async def read_step_result(
    thread: ThreadDep, part_id: str, session: SessionDep
) -> StepResult:
    step = await stored_step_of(session, thread, part_id, every_engine())
    state = step.get("state") or {}
    error = state.get("error")
    return StepResult(
        output=tool_output(state),
        error=None if error is None else error.get("message") or error.get("type"),
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
