"""The tools offered to opencode, and one call to them."""

from typing import Any

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.tool_endpoint import replies
from modules.agent.tool_endpoint.search_sources import SEARCH_SOURCES
from modules.agent.tool_endpoint.tool import Tool, ToolCallError

TOOLS: dict[str, Tool] = {tool.listing["name"]: tool for tool in (SEARCH_SOURCES,)}


def listings() -> list[dict[str, Any]]:
    """What `tools/list` shows: each tool's name, description and input schema."""
    return [tool.listing for tool in TOOLS.values()]


async def call(
    message: dict[str, Any], params: dict[str, Any], session: Session, workspace_id: int
) -> dict[str, Any]:
    """Run one tool; a refusal is a result the model reads, not a protocol error."""
    tool = TOOLS.get(params.get("name", ""))
    if tool is None:
        return replies.error(
            message, replies.INVALID_PARAMS, f"no tool {params.get('name')!r}"
        )
    arguments = params.get("arguments") or {}
    try:
        text = await transact(session, tool.run, workspace_id, arguments)
    except ToolCallError as refused:
        return replies.result(message, _content(str(refused), is_error=True))
    return replies.result(message, _content(text, is_error=False))


def _content(text: str, *, is_error: bool) -> dict[str, Any]:
    """A tool result: one text item, which opencode passes to the model as it is."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}
