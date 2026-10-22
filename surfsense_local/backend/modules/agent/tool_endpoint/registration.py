"""Telling a thread's opencode instance where its tools are, before each of its turns.

opencode names neither thread nor turn when it calls a tool, so each thread
registers an address naming it, in the instance its own folder runs; two
threads' turns at once each keep their own. opencode forgets it on every
reload, so each turn gives it again unless the instance holds it connected,
as given: the address and this API process's launch key.
"""

import logging
from pathlib import Path

import httpx

from api.config import get_settings
from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.connect_limit import OPENCODE_CONNECT_SECONDS
from modules.agent.plugin_tools.given_servers import (
    given_as,
    remember_given,
    server_digest,
)

# The tools reach the model as `<server>_<tool>`: surfsense_search_sources.
SERVER = "surfsense"
# A tool call's hard limit: opencode's own is 12 hours, and progress no longer
# extends it. A render waits up to 150 s for its job, then up to 30 s for a Word
# preview, inside render_document.CALL_SECONDS.
TOOL_CALL_SECONDS = 200
# A call to a plugin on SurfSense's plugin host: a scrape can run minutes.
PLUGIN_CALL_SECONDS = 300

logger = logging.getLogger(__name__)


def thread_tools_url(workspace_id: int, thread_id: int) -> str:
    """The address naming one thread, as an engine is given it."""
    api = get_settings()
    return (
        f"http://{api.host}:{api.port}/agent/tools/workspaces/{workspace_id}"
        f"/threads/{thread_id}"
    )


async def register_thread_tools(
    client: OpencodeClient,
    folder: Path,
    workspace_id: int,
    thread_id: int,
    launch_key: str,
    held: str | None = None,
) -> bool:
    """Give the thread folder's opencode instance this thread's tools; whether they were given now.

    `held` is the status opencode reports for them, if it holds them. A turn goes
    on without the tools if they cannot be given.
    """
    url = thread_tools_url(workspace_id, thread_id)
    headers = {"Authorization": f"Bearer {launch_key}"}
    as_given = server_digest(url, headers)
    if held == "connected" and given_as(folder, SERVER) == as_given:
        return False
    try:
        status = await client.add_tool_server(
            folder,
            SERVER,
            url,
            headers,
            timeout_seconds=TOOL_CALL_SECONDS,
            connect_seconds=OPENCODE_CONNECT_SECONDS,
        )
    except httpx.HTTPError:
        remember_given(folder, SERVER, None)
        logger.warning(
            "thread %s's turn runs without SurfSense's tools", thread_id, exc_info=True
        )
        return True
    remember_given(folder, SERVER, as_given)
    if status != "connected":
        logger.warning(
            "thread %s's turn runs without SurfSense's tools: opencode reports %s",
            thread_id,
            status,
        )
    return True
