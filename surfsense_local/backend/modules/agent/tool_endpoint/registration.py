"""Telling opencode where one workspace's tools are, before each turn there.

opencode names neither workspace nor turn when it calls a tool, so each turn
gives its workspace's folder an address of its own, carrying the turn's scope;
opencode forgets it on every reload, so it is given again before every turn.
Two turns running at once in one workspace share the address registered last.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlencode

import httpx

from api.config import get_settings
from modules.agent.opencode_client import OpencodeClient
from modules.agent.tool_endpoint.turn_scope import PARAMETER, remember_turn_scope

# The tools reach the model as `<server>_<tool>`: surfsense_search_sources.
SERVER = "surfsense"
# Unset, a tool call gets the MCP SDK's 60 s (opencode's own 30 s default covers
# connecting and listing only). A render waits up to 150 s for its job, then up
# to 30 s for a Word preview, inside render_document.CALL_SECONDS.
TOOL_CALL_SECONDS = 200

logger = logging.getLogger(__name__)


async def register_workspace_tools(
    client: OpencodeClient,
    folder: Path,
    workspace_id: int,
    launch_key: str,
    document_ids: Sequence[int] | None,
) -> None:
    """Give the folder's opencode this workspace's tools, kept to the turn's ticked sources.

    `document_ids` None is the whole workspace. A turn goes on without the
    tools if they cannot be given.
    """
    api = get_settings()
    token = remember_turn_scope(workspace_id, document_ids)
    url = (
        f"http://{api.host}:{api.port}/agent/tools/workspaces/{workspace_id}"
        f"?{urlencode({PARAMETER: token})}"
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
