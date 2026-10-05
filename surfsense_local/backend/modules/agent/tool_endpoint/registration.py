"""Telling a thread's opencode instance where its tools are, before each of its turns.

opencode names neither thread nor turn when it calls a tool, so each thread
registers an address naming it, in the instance its own folder runs; two
threads' turns at once each keep their own. opencode forgets it on every
reload, so it is given again before every turn.
"""

import logging
from pathlib import Path

import httpx

from api.config import get_settings
from modules.agent.opencode_client import OpencodeClient

# The tools reach the model as `<server>_<tool>`: surfsense_search_sources.
SERVER = "surfsense"
# Unset, a tool call gets the MCP SDK's 60 s (opencode's own 30 s default covers
# connecting and listing only). A render waits up to 150 s for its job, then up
# to 30 s for a Word preview, inside render_document.CALL_SECONDS.
TOOL_CALL_SECONDS = 200

logger = logging.getLogger(__name__)


async def register_thread_tools(
    client: OpencodeClient,
    folder: Path,
    workspace_id: int,
    thread_id: int,
    launch_key: str,
) -> None:
    """Give the thread folder's opencode instance this thread's tools.

    A turn goes on without the tools if they cannot be given.
    """
    api = get_settings()
    url = (
        f"http://{api.host}:{api.port}/agent/tools/workspaces/{workspace_id}"
        f"/threads/{thread_id}"
    )
    try:
        status = await client.add_tool_server(
            folder,
            SERVER,
            url,
            {"Authorization": f"Bearer {launch_key}"},
            timeout_seconds=TOOL_CALL_SECONDS,
        )
    except httpx.HTTPError:
        logger.warning(
            "thread %s's turn runs without SurfSense's tools", thread_id, exc_info=True
        )
        return
    if status != "connected":
        logger.warning(
            "thread %s's turn runs without SurfSense's tools: opencode reports %s",
            thread_id,
            status,
        )
