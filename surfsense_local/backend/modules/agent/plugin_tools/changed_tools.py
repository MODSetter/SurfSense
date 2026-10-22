"""Each ready plugin is listed again now and then, so a tool its server changed is blocked before the model sees it.

At most once per plugin every CHECK_SECONDS since its last check, connecting included,
before a turn, which waits on it at most DEADLINE_SECONDS: a listing still running then
is recorded when it ends, and the turn keeps what was recorded, as for a server that
cannot be listed. After a turn, plugins last checked AFTER_TURN_SECONDS ago are listed
in the background, so the next turn rarely waits; checks follow the user's turns, never
a timer. A server that cannot be listed keeps what was recorded, and the check says
why; opencode reports it unreachable to the turn. A plugin recorded on the older SSE
transport is never ready, so it is never checked: it stays until the user replaces it.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from api.dependencies import transact
from modules.plugins.gateway.listing import list_tools
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.oauth.listed_after_refresh import (
    listed_after_refresh,
)
from modules.plugins.remote.sign_in.plugin_headers import sign_in_headers
from modules.plugins.remote.source import RemoteMcpSource

CHECK_SECONDS = 300
AFTER_TURN_SECONDS = 200
DEADLINE_SECONDS = 3.0

logger = logging.getLogger(__name__)

# Each plugin's check while it runs, so a turn waits on one already started
# rather than listing the server twice. Also holds the task until it ends.
_checking: dict[str, asyncio.Task[None]] = {}
_after_turn: set[asyncio.Task[int]] = set()


async def check_changed_tools(
    sessions: sessionmaker[Session],
    *,
    older_than: float | None = None,
    deadline: float | None = DEADLINE_SECONDS,
) -> int:
    """Check the ready plugins last checked `older_than` seconds ago, CHECK_SECONDS unless given.

    How many were recorded within `deadline` seconds; None waits for them all.
    """
    older_than = CHECK_SECONDS if older_than is None else older_than
    with sessions() as session:
        due = await transact(session, _due, older_than)
    checks = [
        _checking.get(plugin_id) or _start(sessions, plugin_id, url, headers)
        for plugin_id, url, headers in due
    ]
    if not checks:
        return 0
    done, late = await asyncio.wait(checks, timeout=deadline)
    if late:
        logger.warning(
            "%d plugin(s) not listed within %s s: the turn keeps their recorded tools",
            len(late),
            deadline,
        )
    return len(done)


def check_after_turn(sessions: sessionmaker[Session]) -> None:
    """Start the check of plugins last checked AFTER_TURN_SECONDS ago, and return at once."""
    task = asyncio.create_task(_checked_after_turn(sessions))
    _after_turn.add(task)
    task.add_done_callback(_after_turn.discard)


async def _checked_after_turn(sessions: sessionmaker[Session]) -> int:
    try:
        return await check_changed_tools(
            sessions, older_than=AFTER_TURN_SECONDS, deadline=None
        )
    except Exception:
        logger.warning("plugins were not checked after a turn", exc_info=True)
        return 0


def _start(
    sessions: sessionmaker[Session],
    plugin_id: str,
    url: str,
    headers: dict[str, str],
) -> asyncio.Task[None]:
    task = asyncio.create_task(_check(sessions, plugin_id, url, headers))
    _checking[plugin_id] = task
    task.add_done_callback(lambda _: _checking.pop(plugin_id, None))
    return task


async def _check(
    sessions: sessionmaker[Session],
    plugin_id: str,
    url: str,
    headers: dict[str, str],
) -> None:
    """List and record one plugin, in a session of its own: it may outlive the turn."""
    try:
        listed = await _listed(url, headers)
        with sessions() as session:
            # An OAuth plugin's 401: one refresh, and the listing again.
            listed = await listed_after_refresh(session, plugin_id, headers, listed)
            await transact(session, _record, plugin_id, listed)
    except Exception:
        logger.warning("%s's check was not recorded", plugin_id, exc_info=True)


def _due(session: Session, older_than: float) -> list[tuple[str, str, dict[str, str]]]:
    # SQLite hands datetimes back without their zone; they are stored in UTC.
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=older_than)
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
        logger.warning("%s could not be listed for a check", url, exc_info=True)
        return error
    finally:
        await source.close()


def _record(
    session: Session,
    plugin_id: str,
    listed: list[SourceTool] | ServerError,
) -> None:
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is not None:
        record_check(session, plugin, listed)
