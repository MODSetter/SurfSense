"""Before a turn, each ready plugin is listed again, so a tool its server changed is blocked before the model sees it.

At most once per plugin every CHECK_SECONDS since its last check, connecting included:
a listing is a handshake the turn waits on. A server that cannot be listed keeps what
was recorded, and the check says why; opencode reports it unreachable to the turn.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.plugins.gateway.listing import list_tools
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.plugin_headers import sign_in_headers
from modules.plugins.remote.source import RemoteMcpSource

CHECK_SECONDS = 300

logger = logging.getLogger(__name__)


async def check_changed_tools(session: Session) -> None:
    due = await transact(session, _due)
    listings = await asyncio.gather(*(_listed(*plugin) for _, *plugin in due))
    for (plugin_id, *_), listed in zip(due, listings, strict=True):
        await transact(session, _record, plugin_id, listed)


def _due(session: Session) -> list[tuple[str, str, dict[str, str]]]:
    # SQLite hands datetimes back without their zone; they are stored in UTC.
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=CHECK_SECONDS)
    due = []
    for plugin_id in dict.fromkeys(tool.plugin_id for tool in list_tools(session)):
        plugin = session.get_one(InstalledPlugin, plugin_id)
        checked = plugin.checked_at
        if checked is not None and checked.replace(tzinfo=None) > stale:
            continue
        due.append((plugin_id, plugin.url, sign_in_headers(session, plugin)))
    return due


async def _listed(url: str, headers: dict[str, str]) -> list[SourceTool] | ServerError:
    source = RemoteMcpSource(url, headers)
    try:
        return await source.list_tools()
    except ServerError as error:
        logger.warning("%s could not be listed before a turn", url, exc_info=True)
        return error
    finally:
        await source.close()


def _record(
    session: Session, plugin_id: str, listed: list[SourceTool] | ServerError
) -> None:
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is not None:
        record_check(session, plugin, listed)
