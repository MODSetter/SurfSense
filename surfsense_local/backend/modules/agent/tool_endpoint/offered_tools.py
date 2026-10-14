"""The tools offered to opencode, and one call to them."""

import base64
import logging
from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.tool_endpoint import replies
from modules.agent.tool_endpoint.analyze_data import ANALYZE_DATA
from modules.agent.tool_endpoint.convert_document import CONVERT_DOCUMENT
from modules.agent.tool_endpoint.create_artifact import CREATE_ARTIFACT
from modules.agent.tool_endpoint.list_images import LIST_IMAGES
from modules.agent.tool_endpoint.pdf_form import PDF_FORM
from modules.agent.tool_endpoint.pdf_pages import PDF_PAGES
from modules.agent.tool_endpoint.pdf_stamp import PDF_STAMP
from modules.agent.tool_endpoint.read_document import READ_DOCUMENT
from modules.agent.tool_endpoint.render_document import RENDER_DOCUMENT
from modules.agent.tool_endpoint.revise_document import REVISE_DOCUMENT
from modules.agent.tool_endpoint.search_sources import SEARCH_SOURCES
from modules.agent.tool_endpoint.source_pages import SOURCE_PAGES
from modules.agent.tool_endpoint.tool import (
    InlineImage,
    Tool,
    ToolCallError,
    ToolResult,
)
from modules.agent.tool_endpoint.turn_scope import TurnScope
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

IMAGES_LEFT_OUT = (
    "The images were left out: the selected model cannot read images. Work from "
    "the text above instead."
)

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
        CONVERT_DOCUMENT,
        REVISE_DOCUMENT,
        ANALYZE_DATA,
        PDF_PAGES,
        PDF_STAMP,
        PDF_FORM,
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
    arguments = without_placeholder_ids(tool.listing, params.get("arguments") or {})
    try:
        # Even a tool needing no sources writes into, or reads for, its thread.
        scope.require_known()
        if tool.needs_image_input and not _model_sees_images():
            raise ToolCallError(
                "The selected model cannot read images, so this tool cannot show it "
                "anything. Work from the sources' text instead."
            )
        if tool.waits:
            made = await run_in_threadpool(tool.run, session, scope, arguments)
        else:
            made = await transact(session, tool.run, scope, arguments)
    except ToolCallError as refused:
        return replies.result(message, _content(str(refused), (), is_error=True))
    if isinstance(made, ToolResult):
        return replies.result(message, _content(made.text, made.images, is_error=False))
    return replies.result(message, _content(made, (), is_error=False))


def without_placeholder_ids(
    listing: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """The call's arguments with an optional id of 0 taken as left out.

    OpenAI's models fill every field a tool lists, so an id they do not mean
    arrives as 0: a render then asked for source 0 as its template, was refused,
    and the model sent the same call again. Ids count from 1, so 0 names nothing.
    """
    schema = listing.get("inputSchema") or {}
    required = set(schema.get("required") or ())
    placeholders = {
        name
        for name, spec in (schema.get("properties") or {}).items()
        if name.endswith("_id")
        and name not in required
        and (spec or {}).get("type") == "integer"
    }
    return {
        name: value
        for name, value in arguments.items()
        if not (name in placeholders and value == 0 and not isinstance(value, bool))
    }


def _model_sees_images() -> bool:
    """Read from the configuration opencode runs with, as the previews are."""
    return declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE)


def _content(
    text: str, images: tuple[InlineImage, ...], *, is_error: bool
) -> dict[str, Any]:
    """A tool result: one text item, which opencode passes to the model as it is,
    then the images: on /chat/completions opencode attaches them after the step,
    on /responses it keeps them in the call's output.

    The model must still read images now: opencode turns each image sent to one
    that cannot into an error it is told to report.
    """
    if images and not _model_sees_images():
        logger.warning(
            "dropped %d image(s) from a tool result: the model reads no images now",
            len(images),
        )
        # The text says images come with it; the model must learn none did.
        text, images = f"{text}\n{IMAGES_LEFT_OUT}", ()
    items: list[dict[str, Any]] = [{"type": "text", "text": text}]
    items += [
        {
            "type": "image",
            "data": base64.b64encode(image.data).decode("ascii"),
            "mimeType": image.mime,
        }
        for image in images
    ]
    return {"content": items, "isError": is_error}
