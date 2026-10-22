"""The routes a runtime's MCP client calls for one of a thread's plugins."""

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.dependencies import SessionDep, transact
from modules.agent.plugin_gateway.blocked_call import blocked_reply
from modules.agent.plugin_gateway.expired_token import sent_with_fresh_token
from modules.agent.plugin_gateway.forwarded import send_on, streamed_back, unreachable
from modules.agent.plugin_gateway.gateway_key import require_gateway_key
from modules.agent.plugin_gateway.grown_on_call import grow_on_call
from modules.agent.plugin_gateway.host_calls import HOST_CALLS, Host
from modules.agent.plugin_gateway.missing_scopes import note_missing_scopes
from modules.agent.plugin_gateway.ready_upstream import Upstream, ready_upstream
from modules.agent.plugin_gateway.recorded_call import record_call
from modules.agent.plugin_gateway.refused_elicitation import without_elicitation
from modules.agent.plugin_tools.stop_plugin_calls import origin
from modules.agent.plugin_tools.thread_calls import CALLS_HEADER
from modules.agent.tool_endpoint.allowed_callers import refuse_web_pages
from modules.usage_statistics.activity_counts import count_plugin_calls

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
    if request.method == "GET":
        # The stream a server would send unasked messages on, which SurfSense uses none of:
        # MCP lets a client do without it, and one held open kept Claude Code from quitting.
        return Response(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            headers={"allow": "POST, DELETE"},
        )
    return await _forwarded(session, request, (plugin_id, thread_id), upstream)


async def _ready(session: SessionDep, plugin_id: str, thread_id: int) -> Upstream:
    upstream = await transact(session, ready_upstream, plugin_id, thread_id)
    if upstream is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this plugin is not ready")
    return upstream


async def _forwarded(
    session: SessionDep, request: Request, where: tuple[str, int], upstream: Upstream
) -> Response:
    body = without_elicitation(await request.body())
    refused = blocked_reply(body, upstream.tools)
    if refused is not None:
        return refused
    host = _host(upstream)
    call = HOST_CALLS.sent(host, body, upstream.headers) if host else None
    answered = (lambda: HOST_CALLS.answered(host, call)) if call is not None else None
    await record_call(session, upstream.url)
    try:
        sent = await send_on(request, body, upstream.url, upstream.headers)
        # Counted once it reached the plugin, before a token refresh may resend it.
        await count_plugin_calls(body)
        sent = await sent_with_fresh_token(
            session, where, request, body, upstream, sent
        )
    except httpx2.HTTPError:
        if answered is not None:
            answered()
        return unreachable()
    await note_missing_scopes(session, request, where, sent)
    await grow_on_call(where[1], where[0], body)
    return streamed_back(sent, then=answered)


def _host(upstream: Upstream) -> Host | None:
    """Where the thread's calls run on SurfSense's plugin host; None for any other server."""
    token = upstream.headers.get(CALLS_HEADER)
    if token is None:
        return None
    return (origin(upstream.url), upstream.headers.get("authorization", ""), token)
