"""Before a turn: the folder's opencode holds exactly the ready plugins; the session's
rules, which tool_exposure/ writes, say which of their tools it may call.

The servers are given all at once, each within CONNECT_SECONDS, so a turn waits for the
slowest rather than the sum, and a server that hangs is named unavailable alone.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.connect_limit import (
    CONNECT_SECONDS,
    OPENCODE_CONNECT_SECONDS,
)
from modules.agent.plugin_tools.given_servers import digest, given_as, remember_given
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin
from modules.agent.tool_endpoint.registration import (
    PLUGIN_CALL_SECONDS,
    SERVER,
    TOOL_CALL_SECONDS,
)

logger = logging.getLogger(__name__)

_SIGN_IN = {"needs_auth", "needs_client_registration"}


@dataclass(frozen=True)
class Given:
    """The ready plugins opencode could not connect to, how many servers were given now,
    and each server whose giving failed, by name and digest."""

    unavailable: list[UnavailablePlugin]
    added: int
    failed: frozenset[tuple[str, str]] = frozenset()


async def give_plugins(
    client: OpencodeClient,
    folder: Path,
    held: dict[str, str],
    plugins: list[TurnPlugin],
    failed: frozenset[tuple[str, str]] = frozenset(),
) -> Given:
    """Drop the held servers no longer ready, then give the ready ones not held as they are.

    `held` is each server the folder's opencode holds, with its status, as
    `tool_servers` reports it; it is kept up to date here. A server in `failed`,
    as an earlier giving this turn left it, is named unreachable without a second wait.
    """
    ready = {plugin.name for plugin in plugins}
    for name in held.keys() - ready - {SERVER}:
        try:
            await client.drop_tool_server(folder, name)
        except httpx.HTTPError:
            # Its tools stay denied: the rules deny every server opencode holds.
            logger.warning("opencode kept %s in %s", name, folder, exc_info=True)
            continue
        remember_given(folder, name, None)

    async def give(plugin: TurnPlugin) -> tuple[str, bool]:
        status = held.get(plugin.name)
        if status == "connected" and given_as(folder, plugin.name) == digest(plugin):
            return status, False
        if (plugin.name, digest(plugin)) in failed:
            return "failed", False
        try:
            status = await asyncio.wait_for(
                client.add_tool_server(
                    folder,
                    plugin.name,
                    plugin.url,
                    plugin.headers,
                    timeout_seconds=(
                        PLUGIN_CALL_SECONDS
                        if plugin.on_plugin_host
                        else TOOL_CALL_SECONDS
                    ),
                    connect_seconds=OPENCODE_CONNECT_SECONDS,
                ),
                CONNECT_SECONDS,
            )
        except (httpx.HTTPError, TimeoutError):
            logger.warning(
                "opencode could not connect %s in %s",
                plugin.name,
                folder,
                exc_info=True,
            )
            return "failed", False
        held[plugin.name] = status
        remember_given(folder, plugin.name, digest(plugin))
        return status, True

    given = await asyncio.gather(*(give(plugin) for plugin in plugins))
    unavailable = []
    for plugin, (status, _) in zip(plugins, given, strict=True):
        if status in _SIGN_IN:
            reason = "license" if plugin.licensed else "sign_in"
            unavailable.append(UnavailablePlugin(plugin.title, reason))
        elif status != "connected":
            unavailable.append(UnavailablePlugin(plugin.title, "unreachable"))
    failed |= {
        (plugin.name, digest(plugin))
        for plugin, (status, _) in zip(plugins, given, strict=True)
        if status == "failed"
    }
    return Given(unavailable, sum(added for _, added in given), failed)


def servers(plugins: list[TurnPlugin]) -> list[tuple[str, str]]:
    """What giving `plugins` sends opencode: two lists alike need no second giving."""
    return [(plugin.name, digest(plugin)) for plugin in plugins]
