"""The route opencode's MCP client calls for one workspace's tools."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import JSONResponse

from api.dependencies import SessionDep
from modules.agent.launch_key import require_launch_key
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages
from modules.agent.tool_endpoint.messages import answer
from modules.agent.tool_endpoint.protocol_version import refuse_unknown_protocol
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


@router.post("/workspaces/{workspace_id}", summary="Answer opencode's MCP client")
async def answer_tools(
    workspace: WorkspaceDep,
    message: Annotated[dict[str, Any], Body()],
    session: SessionDep,
) -> Response:
    """One JSON-RPC message in, its reply out; the workspace scopes every tool."""
    reply = await answer(message, session, workspace.id)
    if reply is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return JSONResponse(reply)
