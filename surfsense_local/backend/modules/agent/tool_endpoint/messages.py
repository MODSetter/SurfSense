"""Each message opencode sends, and what it gets back.

Stateless and JSON only (MCP 2025-11-25, Streamable HTTP): every request is
answered in the response to its own POST, and nothing is kept between them.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint import offered_tools, plugin_asks, replies
from modules.agent.tool_endpoint.protocol_version import initialized
from modules.agent.tool_endpoint.turn_scope import TurnScope


async def answer(
    message: dict[str, Any],
    session: Session,
    scope: Callable[[], Awaitable[TurnScope]],
    asks_for: int | None = None,
) -> dict[str, Any] | None:
    """The reply to one message; None for a notification, which gets none.

    `scope` is read for a listing and a tool call. `asks_for` is the thread whose
    opencode turn may ask for the plugin tools it does not hold; None for Claude Code.
    """
    if "id" not in message:
        return None
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        catalogue = ""
        if asks_for is not None:
            catalogue = (await plugin_asks.plugin_tools(session)).catalogue()
        return replies.result(message, initialized(params, catalogue))
    if method == "tools/list":
        tools = offered_tools.listings(await scope())
        if asks_for is not None:
            tools += await plugin_asks.ask_listings(session)
        return replies.result(message, {"tools": tools})
    if method == "tools/call":
        if asks_for is not None:
            asked = await plugin_asks.ask(message, params, asks_for)
            if asked is not None:
                return asked
        return await offered_tools.call(message, params, session, await scope())
    if method == "ping":
        return replies.result(message, {})
    return replies.error(message, replies.UNKNOWN_METHOD, f"no method {method!r}")
