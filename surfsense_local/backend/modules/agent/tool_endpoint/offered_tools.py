"""The tools offered to opencode, and one call to them."""

from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.tool_endpoint import replies
from modules.agent.tool_endpoint.create_artifact import CREATE_ARTIFACT
from modules.agent.tool_endpoint.list_images import LIST_IMAGES
from modules.agent.tool_endpoint.read_document import READ_DOCUMENT
from modules.agent.tool_endpoint.render_document import RENDER_DOCUMENT
from modules.agent.tool_endpoint.search_sources import SEARCH_SOURCES
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope

# In a fixed order, so a local model's prompt cache holds from turn to turn.
TOOLS: dict[str, Tool] = {
    tool.listing["name"]: tool
    for tool in (
        SEARCH_SOURCES,
        CREATE_ARTIFACT,
        RENDER_DOCUMENT,
        READ_DOCUMENT,
        LIST_IMAGES,
    )
}


def listings() -> list[dict[str, Any]]:
    """What `tools/list` shows: each tool's name, description and input schema."""
    return [tool.listing for tool in TOOLS.values()]


async def call(
    message: dict[str, Any], params: dict[str, Any], session: Session, scope: TurnScope
) -> dict[str, Any]:
    """Run one tool; a refusal is a result the model reads, not a protocol error."""
    tool = TOOLS.get(params.get("name", ""))
    if tool is None:
        return replies.error(
            message, replies.INVALID_PARAMS, f"no tool {params.get('name')!r}"
        )
    arguments = params.get("arguments") or {}
    try:
        if tool.waits:
            text = await run_in_threadpool(tool.run, session, scope, arguments)
        else:
            text = await transact(session, tool.run, scope, arguments)
    except ToolCallError as refused:
        return replies.result(message, _content(str(refused), is_error=True))
    return replies.result(message, _content(text, is_error=False))


def _content(text: str, *, is_error: bool) -> dict[str, Any]:
    """A tool result: one text item, which opencode passes to the model as it is."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}
