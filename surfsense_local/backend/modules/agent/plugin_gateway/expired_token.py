"""An OAuth plugin's `401` mid-session: its token refreshed once and the request sent again.

The runtime never sees the refusal and keeps its MCP session. A refused refresh marks the
plugin to sign in again, names it in the running turn, and the `401` goes back.
"""

from sqlalchemy.orm import Session
from starlette.requests import Request

from api.dependencies import transact
from modules.agent.plugin_gateway.forwarded import Sent, send_on
from modules.agent.plugin_gateway.ready_upstream import Upstream, ready_upstream
from modules.agent.plugin_gateway.turn_notice import tell_turn
from modules.plugins.remote.sign_in.oauth.token_refresh import Refresh, refresh_sign_in


async def sent_with_fresh_token(
    session: Session,
    where: tuple[str, int],
    request: Request,
    body: bytes,
    upstream: Upstream,
    sent: Sent,
) -> Sent:
    if sent.answer.status_code != 401 or not upstream.oauth:
        return sent
    plugin_id, thread_id = where
    refused = upstream.headers.get("authorization", "").removeprefix("Bearer ")
    refreshed = await refresh_sign_in(session, plugin_id, refused_token=refused)
    if refreshed == Refresh.SIGNED_OUT:
        tell_turn(request, thread_id, upstream.title, "sign_in")
    if refreshed != Refresh.REFRESHED:
        return sent
    renewed = await transact(session, ready_upstream, plugin_id, thread_id)
    if renewed is None:
        return sent
    await sent.close()
    return await send_on(request, body, renewed.url, renewed.headers)
