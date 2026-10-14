"""Before a turn: the folder's opencode holds exactly the ready plugins, and the session's rules say what each tool may do."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.given_servers import digest, given_as, remember_given
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.tool_endpoint.registration import SERVER, TOOL_CALL_SECONDS

logger = logging.getLogger(__name__)

_SIGN_IN = {"needs_auth", "needs_client_registration"}


@dataclass(frozen=True)
class UnavailablePlugin:
    title: str
    reason: Literal["unreachable", "sign_in", "license"]


async def give_plugins(
    client: OpencodeClient, folder: Path, session_id: str, plugins: list[TurnPlugin]
) -> list[UnavailablePlugin]:
    """The ready plugins opencode could not connect to. A turn goes on without plugins if opencode fails here."""
    try:
        return await _give(client, folder, session_id, plugins)
    except httpx.HTTPError:
        logger.warning("%s's turn runs without plugins", folder, exc_info=True)
        return []


async def _give(
    client: OpencodeClient, folder: Path, session_id: str, plugins: list[TurnPlugin]
) -> list[UnavailablePlugin]:
    held = await client.tool_servers(folder)
    ready = {plugin.name for plugin in plugins}
    for name in held.keys() - ready - {SERVER}:
        await client.drop_tool_server(folder, name)
        remember_given(folder, name, None)

    unavailable = []
    for plugin in plugins:
        status = held.get(plugin.name)
        if status != "connected" or given_as(folder, plugin.name) != digest(plugin):
            status = await client.add_tool_server(
                folder,
                plugin.name,
                plugin.url,
                plugin.headers,
                timeout_seconds=TOOL_CALL_SECONDS,
            )
            remember_given(folder, plugin.name, digest(plugin))
        if status in _SIGN_IN:
            reason = "license" if plugin.licensed else "sign_in"
            unavailable.append(UnavailablePlugin(plugin.title, reason))
        elif status != "connected":
            unavailable.append(UnavailablePlugin(plugin.title, "unreachable"))

    # Each server opencode holds is denied first, so a tool SurfSense has not
    # reviewed is refused and left out of what the model is offered.
    rules = [_rule(f"{name}_*", "deny") for name in held.keys() - {SERVER} | ready]
    for plugin in plugins:
        rules += [_rule(tool, action) for tool, action in plugin.rules.items()]
    await client.set_session_rules(folder, session_id, rules)
    return unavailable


def _rule(permission: str, action: str) -> dict[str, str]:
    return {"permission": permission, "pattern": "*", "action": action}
