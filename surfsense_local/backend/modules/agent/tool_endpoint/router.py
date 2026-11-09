"""The route opencode's MCP client calls for one agent thread's tools."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import JSONResponse

from api.dependencies import SessionDep, transact
from modules.agent.launch_key import require_launch_key
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages
from modules.agent.tool_endpoint.messages import answer
from modules.agent.tool_endpoint.protocol_version import refuse_unknown_protocol
from modules.agent.tool_endpoint.registration import OPENCODE
from modules.agent.tool_endpoint.turn_scope import TurnScope, thread_turn_scope
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(
    prefix="/agent/tools",
    tags=["agent"],
    dependencies=[
        Depends(refuse_web_pages),
        Depends(require_launch_key),
        Depends(refuse_unknown_protocol),
    ],
)


@router.post(
    "/workspaces/{workspace_id}/threads/{thread_id}",
    summary="Answer opencode's MCP client for one thread",
)
async def answer_tools(
    workspace: WorkspaceDep,
    thread_id: int,
    message: Annotated[dict[str, Any], Body()],
    session: SessionDep,
    engine: str | None = None,
) -> Response:
    """One JSON-RPC message in, its reply out; the thread's sources scope every tool.

    opencode's address names it as the engine: only its turns hold some plugin tools.
    """

    async def scope() -> TurnScope:
        # Read only for a tool call: listing and pings need no transaction.
        return await transact(session, thread_turn_scope, workspace.id, thread_id)

    asks_for = thread_id if engine == OPENCODE else None
    reply = await answer(message, session, scope, asks_for)
    if reply is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return JSONResponse(reply)
