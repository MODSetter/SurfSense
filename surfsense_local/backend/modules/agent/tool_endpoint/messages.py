"""Each message opencode sends, and what it gets back.

Stateless and JSON only (MCP 2025-11-25, Streamable HTTP): every request is
answered in the response to its own POST, and nothing is kept between them.
"""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint import offered_tools, replies
from modules.agent.tool_endpoint.protocol_version import initialized


async def answer(
    message: dict[str, Any], session: Session, workspace_id: int
) -> dict[str, Any] | None:
    """The reply to one message; None for a notification, which gets none."""
    if "id" not in message:
        return None
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        return replies.result(message, initialized(params))
    if method == "tools/list":
        return replies.result(message, {"tools": offered_tools.listings()})
    if method == "tools/call":
        return await offered_tools.call(message, params, session, workspace_id)
    if method == "ping":
        return replies.result(message, {})
    return replies.error(message, replies.UNKNOWN_METHOD, f"no method {method!r}")
