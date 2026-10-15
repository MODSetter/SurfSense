"""Before a turn, an OAuth plugin's token that expires within half an hour is refreshed.

Longer than any turn runs, so opencode never holds an expired token mid-reply. A changed
token changes the header, so the plugin is given to opencode again (`given_servers.py`).
"""

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.plugin_tools.give_plugins import UnavailablePlugin
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH
from modules.plugins.remote.sign_in.oauth.token_refresh import Refresh, refresh_sign_in

REFRESH_WITHIN_SECONDS = 30 * 60


async def refresh_sign_ins(session: Session) -> list[UnavailablePlugin]:
    """The plugins whose refresh was refused: no longer ready, named to the user."""
    signed_out = []
    for plugin_id, title in await transact(session, _ready_oauth_plugins):
        refreshed = await refresh_sign_in(
            session, plugin_id, within_seconds=REFRESH_WITHIN_SECONDS
        )
        if refreshed == Refresh.SIGNED_OUT:
            signed_out.append(UnavailablePlugin(title, "sign_in"))
    return signed_out


def _ready_oauth_plugins(session: Session) -> list[tuple[str, str]]:
    ready = {tool.plugin_id: tool.plugin_name for tool in list_tools(session)}
    return [
        (plugin_id, title)
        for plugin_id, title in ready.items()
        if session.get_one(InstalledPlugin, plugin_id).credential_kind == OAUTH
    ]
