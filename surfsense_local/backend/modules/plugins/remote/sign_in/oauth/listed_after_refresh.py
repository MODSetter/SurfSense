"""A listing an OAuth plugin's server refused with `401`: refreshed once, then listed again."""

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.oauth.token_refresh import Refresh, refresh_sign_in
from modules.plugins.remote.sign_in.plugin_headers import sign_in_headers
from modules.plugins.remote.source import RemoteMcpSource

Listed = list[SourceTool] | ServerError


async def list_once(url: str, headers: dict[str, str]) -> Listed:
    source = RemoteMcpSource(url, headers)
    try:
        return await source.list_tools()
    except ServerError as error:
        return error
    finally:
        await source.close()


async def listed_after_refresh(
    session: Session, plugin_id: str, headers: dict[str, str], listed: Listed
) -> Listed:
    """Any other outcome, or a plugin not signed in with OAuth, is returned as it was."""
    if not isinstance(listed, ServerError) or listed.status != 401:
        return listed
    refused = headers.get("authorization", "").removeprefix("Bearer ")
    if (
        await refresh_sign_in(session, plugin_id, refused_token=refused)
        != Refresh.REFRESHED
    ):
        return listed

    def address(s: Session) -> tuple[str, dict[str, str]] | None:
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None:
            return None
        return plugin.url, sign_in_headers(s, plugin)

    found = await transact(session, address)
    return listed if found is None else await list_once(*found)
