"""Telling opencode where one workspace's tools are, before each turn there.

opencode names no workspace when it calls a tool, so each workspace's folder is
given its own address; opencode forgets it on every reload, so it is given again
before every turn.
"""

import logging
from pathlib import Path

import httpx

from api.config import get_settings
from modules.agent.opencode_client import OpencodeClient

# The tools reach the model as `<server>_<tool>`: surfsense_search_sources.
SERVER = "surfsense"

logger = logging.getLogger(__name__)


async def register_workspace_tools(
    client: OpencodeClient, folder: Path, workspace_id: int, launch_key: str
) -> None:
    """Give the folder's opencode this workspace's tools; a turn goes on without them if it cannot."""
    api = get_settings()
    url = f"http://{api.host}:{api.port}/agent/tools/workspaces/{workspace_id}"
    try:
        status = await client.add_tool_server(
            folder, SERVER, url, {"Authorization": f"Bearer {launch_key}"}
        )
    except httpx.HTTPError:
        logger.warning(
            "workspace %s's turn runs without SurfSense's tools",
            workspace_id,
            exc_info=True,
        )
        return
    if status != "connected":
        logger.warning(
            "workspace %s's turn runs without SurfSense's tools: opencode reports %s",
            workspace_id,
            status,
        )
