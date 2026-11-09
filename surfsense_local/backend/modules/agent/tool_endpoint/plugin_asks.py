"""What opencode's agent has of the plugin tools its turn does not hold.

When they do not all fit, SurfSense's server tells the agent every ready plugin in its
instructions, and lists two tools that hold more: one plugin by its name, or the
plugin of the tool that best fits what the agent wants to do. Each writes the
session's rules before it answers, so the tools are the agent's at its next step.
Claude Code holds every tool, and is shown none of this.
"""

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.agent.tool_endpoint import replies
from modules.agent.tool_endpoint.offered_tools import TOOLS
from modules.agent.tool_exposure import holdings
from modules.agent.tool_exposure.growing import grow_by_search, hold_plugins
from modules.agent.tool_exposure.holdings import Holding
from modules.agent.tool_exposure.loaded_steps import loaded_reply
from modules.agent.tool_exposure.turn_tools import TurnTools, turn_tools

logger = logging.getLogger(__name__)

OPEN_PLUGIN: dict[str, Any] = {
    "name": "open_plugin",
    "description": (
        "Load all of a connected plugin's tools, by the plugin's name or its @id from "
        "the list of plugins. They are yours from your next step."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "plugin": {"type": "string", "description": "The plugin's name or @id."}
        },
        "required": ["plugin"],
    },
}

FIND_TOOLS: dict[str, Any] = {
    "name": "find_tools",
    "description": (
        "Find and load the plugin tools for something you want to do, when no tool "
        "you hold does it. They are yours from your next step."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What you want to do, in a sentence.",
            }
        },
        "required": ["query"],
    },
}

ASKS = (OPEN_PLUGIN, FIND_TOOLS)
# SurfSense's own tools, the two above among them, counted against a provider's limit.
SURFSENSE_TOOLS = len(TOOLS) + len(ASKS)

_NO_TURN = "No request is running, so no plugin tools can be loaded now."
_UNREACHABLE = "The plugin tools could not be loaded now. Go on without them."


async def plugin_tools(session: Session) -> TurnTools:
    """Every ready plugin tool, and whether a turn holds them all."""
    return await turn_tools(session, SURFSENSE_TOOLS)


async def ask_listings(session: Session) -> list[dict[str, Any]]:
    """The two tools, when the plugin tools do not all fit."""
    return [] if (await plugin_tools(session)).fit else list(ASKS)


async def ask(
    message: dict[str, Any], params: dict[str, Any], thread_id: int
) -> dict[str, Any] | None:
    """The reply to a call of one of the two tools; None for any other tool."""
    name = params.get("name")
    if name not in (OPEN_PLUGIN["name"], FIND_TOOLS["name"]):
        return None
    arguments = params.get("arguments") or {}
    holding = holdings.holding_of(thread_id)
    if holding is None:
        return _said(message, _NO_TURN, is_error=True)
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return _said(message, _UNREACHABLE, is_error=True)
    try:
        if name == OPEN_PLUGIN["name"]:
            return await _open(message, client, holding, arguments)
        return await _find(message, client, holding, arguments)
    except httpx.HTTPError:
        logger.warning("plugin tools could not be held", exc_info=True)
        return _said(message, _UNREACHABLE, is_error=True)
    finally:
        await client.close()


async def _open(message, client, holding: Holding, arguments) -> dict[str, Any]:
    asked = str(arguments.get("plugin") or "").strip().removeprefix("@").casefold()
    plugin = next(
        (
            p
            for p in holding.plugins
            if asked in (p.name.casefold(), p.title.casefold())
        ),
        None,
    )
    if plugin is None:
        names = ", ".join(f"{p.title} (@{p.name})" for p in holding.plugins)
        return _said(
            message, f"No connected plugin is named that. These are: {names}.", True
        )
    added = await hold_plugins(client, holding, [plugin.name])
    held = sorted(n for n in plugin.rules if n in holding.held)
    if not held:
        return _said(
            message,
            f"{plugin.title}'s tools cannot be loaded: you hold as many tools as the "
            "model takes.",
            True,
        )
    if not added:
        return _said(
            message, f"You already hold {plugin.title}'s tools: {', '.join(held)}."
        )
    return _said(message, loaded_reply(plugin.title, held))


async def _find(message, client, holding: Holding, arguments) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        return _said(message, "Say what you want to do.", True)
    try:
        added = await grow_by_search(client, holding, query, holding.embed)
    except httpx.HTTPError:
        raise
    except Exception:
        # An embedder that cannot run leaves the keyword leg, which still ranks.
        logger.warning("tools were found by keyword alone", exc_info=True)
        added = await grow_by_search(client, holding, query, None)
    if not added:
        return _said(
            message,
            "No plugin tool you do not already hold fits that. Go on with the tools "
            "you have.",
        )
    title = holding.plugin_of(min(added)).title
    return _said(message, loaded_reply(title, sorted(added)))


def _said(message: dict[str, Any], text: str, is_error: bool = False) -> dict[str, Any]:
    return replies.result(
        message, {"content": [{"type": "text", "text": text}], "isError": is_error}
    )
