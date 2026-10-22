"""The routes a runtime's MCP client calls for one of a thread's plugins."""

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.dependencies import SessionDep, transact
from modules.agent.plugin_gateway.blocked_call import blocked_reply
from modules.agent.plugin_gateway.expired_token import sent_with_fresh_token
from modules.agent.plugin_gateway.forwarded import send_on, streamed_back, unreachable
from modules.agent.plugin_gateway.gateway_key import require_gateway_key
from modules.agent.plugin_gateway.missing_scopes import note_missing_scopes
from modules.agent.plugin_gateway.ready_upstream import Upstream, ready_upstream
from modules.agent.plugin_gateway.recorded_call import record_call
from modules.agent.plugin_gateway.sse_endpoint import (
    MESSAGES,
    pointed_back,
    server_path,
)
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages
from modules.plugins.remote.mcp_client.transports import SSE

router = APIRouter(
    prefix="/agent/plugins",
    tags=["agent"],
    dependencies=[Depends(refuse_web_pages), Depends(require_gateway_key)],
)

_PLUGIN = "/workspaces/{workspace_id}/threads/{thread_id}/{plugin_id}"


@router.api_route(
    _PLUGIN,
    methods=["GET", "POST", "DELETE"],
    summary="Forward a runtime's MCP request to a ready plugin's server",
)
async def plugin(
    thread_id: int, plugin_id: str, request: Request, session: SessionDep
) -> Response:
    upstream = await _ready(session, plugin_id, thread_id)
    if request.method == "GET" and upstream.transport != SSE:
        # The stream a server would send unasked messages on, which SurfSense uses none of:
        # MCP lets a client do without it, and one held open kept Claude Code from quitting.
        return Response(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            headers={"allow": "POST, DELETE"},
        )
    return await _forwarded(
        session, request, (plugin_id, thread_id), upstream, upstream.url
    )


@router.post(
    f"{_PLUGIN}/{MESSAGES}",
    summary="Forward a message to a plugin on the older SSE transport",
)
async def sse_message(
    thread_id: int, plugin_id: str, to: str, request: Request, session: SessionDep
) -> Response:
    upstream = await _ready(session, plugin_id, thread_id)
    url = server_path(upstream.url, to)
    if url is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not this plugin's server")
    return await _forwarded(session, request, (plugin_id, thread_id), upstream, url)


async def _ready(session: SessionDep, plugin_id: str, thread_id: int) -> Upstream:
    upstream = await transact(session, ready_upstream, plugin_id, thread_id)
    if upstream is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this plugin is not ready")
    return upstream


async def _forwarded(
    session: SessionDep,
    request: Request,
    where: tuple[str, int],
    upstream: Upstream,
    url: str,
) -> Response:
    body = await request.body()
    refused = blocked_reply(body, upstream.tools, upstream.transport != SSE)
    if refused is not None:
        return refused
    await record_call(session, url)
    try:
        sent = await send_on(request, body, url, upstream.headers)
        sent = await sent_with_fresh_token(
            session, where, request, body, upstream, sent
        )
    except httpx2.HTTPError:
        return unreachable()
    await note_missing_scopes(session, request, where, sent)
    if upstream.transport == SSE and request.method == "GET":
        gateway_url = str(request.url.replace(query=""))
        return streamed_back(
            sent, pointed_back(sent.answer.aiter_bytes(), upstream.url, gateway_url)
        )
    return streamed_back(sent)
