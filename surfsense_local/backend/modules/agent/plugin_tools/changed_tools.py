"""Before a turn, each ready plugin is listed again, so a tool its server changed is blocked before the model sees it.

At most once per plugin every CHECK_SECONDS: a listing is a handshake the turn waits on.
A server that cannot be listed keeps what was recorded; opencode reports it unreachable.
Called from the event loop only.
"""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.plugins.gateway.listing import list_tools
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.recorded_tools import record_tools
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.source import RemoteMcpSource

CHECK_SECONDS = 300

logger = logging.getLogger(__name__)

_checked_at: dict[str, float] = {}


async def check_changed_tools(session: Session) -> None:
    due = await transact(session, _due)
    listings = await asyncio.gather(*(_listed(*plugin) for _, *plugin in due))
    for (plugin_id, *_), tools in zip(due, listings, strict=True):
        if tools is not None:
            await transact(session, _record, plugin_id, tools)


def _due(session: Session) -> list[tuple[str, str, dict[str, str]]]:
    now = time.monotonic()
    due = []
    for plugin_id in dict.fromkeys(tool.plugin_id for tool in list_tools(session)):
        if now - _checked_at.get(plugin_id, -CHECK_SECONDS) < CHECK_SECONDS:
            continue
        # Counted when tried, so a server that is down does not slow every turn.
        _checked_at[plugin_id] = now
        plugin = session.get_one(InstalledPlugin, plugin_id)
        due.append((plugin_id, plugin.url, token_headers(plugin.credential)))
    return due


async def _listed(url: str, headers: dict[str, str]) -> list[SourceTool] | None:
    source = RemoteMcpSource(url, headers)
    try:
        return await source.list_tools()
    except ServerError:
        logger.warning("%s could not be listed before a turn", url, exc_info=True)
        return None
    finally:
        await source.close()


def _record(session: Session, plugin_id: str, tools: list[SourceTool]) -> None:
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is not None:
        record_tools(session, plugin, tools)
