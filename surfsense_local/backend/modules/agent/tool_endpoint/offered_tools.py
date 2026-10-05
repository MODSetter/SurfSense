"""The tools offered to opencode, and one call to them."""

from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.tool_endpoint import replies
from modules.agent.tool_endpoint.create_artifact import CREATE_ARTIFACT
from modules.agent.tool_endpoint.list_images import LIST_IMAGES
from modules.agent.tool_endpoint.read_document import READ_DOCUMENT
from modules.agent.tool_endpoint.render_document import RENDER_DOCUMENT
from modules.agent.tool_endpoint.search_sources import SEARCH_SOURCES
from modules.agent.tool_endpoint.source_pages import SOURCE_PAGES
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from shared.config import get_storage_settings

# In a fixed order, so a local model's prompt cache holds from turn to turn.
TOOLS: dict[str, Tool] = {
    tool.listing["name"]: tool
    for tool in (
        SEARCH_SOURCES,
        CREATE_ARTIFACT,
        RENDER_DOCUMENT,
        READ_DOCUMENT,
        LIST_IMAGES,
        SOURCE_PAGES,
    )
}


def listings() -> list[dict[str, Any]]:
    """What `tools/list` shows: each tool's name, description and input schema.

    A tool returning images is left out for a model that cannot see them.
    """
    sees = _model_sees_images()
    return [
        tool.listing for tool in TOOLS.values() if sees or not tool.needs_image_input
    ]


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
        # Even a tool needing no sources writes into, or reads for, its thread.
        scope.require_known()
        if tool.needs_image_input and not _model_sees_images():
            raise ToolCallError(
                "The selected model cannot read images, so this tool cannot show it "
                "anything. Work from the sources' text instead."
            )
        if tool.waits:
            text = await run_in_threadpool(tool.run, session, scope, arguments)
        else:
            text = await transact(session, tool.run, scope, arguments)
    except ToolCallError as refused:
        return replies.result(message, _content(str(refused), is_error=True))
    return replies.result(message, _content(text, is_error=False))


def _model_sees_images() -> bool:
    """Read from the configuration opencode runs with, as the previews are."""
    return declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE)


def _content(text: str, *, is_error: bool) -> dict[str, Any]:
    """A tool result: one text item, which opencode passes to the model as it is."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}
