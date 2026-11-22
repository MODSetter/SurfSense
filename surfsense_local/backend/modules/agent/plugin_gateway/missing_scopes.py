"""A call refused with `403 insufficient_scope`: recorded as a check records it, and named in
the thread's running turn, whichever runtime made the call. The refusal still goes back."""

from sqlalchemy.orm import Session
from starlette.requests import Request

from api.dependencies import transact
from modules.agent.plugin_gateway.forwarded import Sent
from modules.agent.plugin_gateway.turn_notice import tell_turn
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.mcp_client.scope_challenge import challenged_scopes
from modules.plugins.remote.mcp_client.server_error import ServerError


async def note_missing_scopes(
    session: Session, request: Request, where: tuple[str, int], sent: Sent
) -> None:
    scopes = challenged_scopes(sent.answer)
    if scopes is None:
        return
    plugin_id, thread_id = where
    title = await transact(session, _needs_scopes, plugin_id, scopes)
    tell_turn(request, thread_id, title, "needs_scopes")


def _needs_scopes(session: Session, plugin_id: str, scopes: list[str]) -> str:
    plugin = session.get_one(InstalledPlugin, plugin_id)
    refusal = ServerError("insufficient scope", status=403, scopes=scopes)
    record_check(session, plugin, refusal)
    return plugin.entry.get("name", plugin.id)
