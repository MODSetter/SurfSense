"""The images a page names, made inline as it is kept.

The agent has no shell to encode a picture, and typing base64 through a model is
not practical; the viewer gives a page no network, so a data URL is the only way in.
"""

import base64
import re
from collections import Counter

from sqlalchemy.orm import Session

from modules.agent.previews.inline_images import inline_image
from modules.agent.tool_endpoint.selected_images import refuse_unselected_images
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.drawn_images.names import ImageStillDrawingError
from modules.artifacts.script_documents.script_images import ScriptImage, script_image
from modules.artifacts.web_pages.page_checks import too_large

PREFIX = "surfsense-image:"
_PLACED = re.compile(re.escape(PREFIX) + r"([A-Za-z0-9_-]+)")


def with_placed_images(
    session: Session, scope: TurnScope, page: str, limit: int
) -> str:
    """The page with each named image as a data URL; the refusal if one cannot be had.

    The size is worked out before anything is written: a small file can name one
    picture thousands of times, each a whole data URL.
    """
    named = Counter(_PLACED.findall(page))
    if not named:
        return page
    refuse_unselected_images(scope, named)
    try:
        images = {name: _found(session, scope, name) for name in named}
    finally:
        session.rollback()  # reads only; the files below take no write lock
    size = len(page.encode("utf-8"))
    urls: dict[str, str] = {}
    for name, count in named.items():
        urls[name] = _data_url(name, images[name])
        size += count * (len(urls[name]) - len(PREFIX) - len(name))
        if size > limit:
            raise ToolCallError(str(too_large(size, limit)))
    return _PLACED.sub(lambda placed: urls[placed[1]], page)


def _found(session: Session, scope: TurnScope, name: str) -> ScriptImage:
    thread_id = scope.thread_id if scope.known else None
    try:
        return script_image(session, scope.workspace_id, thread_id, name)
    except ImageStillDrawingError as error:
        raise ToolCallError(
            f'The picture "{name}" is still being drawn. Tell the user the page can '
            "use it once it appears in Studio, and stop."
        ) from error
    except LookupError as error:
        raise _no_image(name) from error


def _data_url(name: str, image: ScriptImage) -> str:
    try:
        # Scaled as a tool result's image is, so a page holds many within its limit.
        shown = inline_image(image())
    except (LookupError, OSError, ValueError) as error:
        raise _no_image(name) from error
    encoded = base64.b64encode(shown.data).decode("ascii")
    return f"data:{shown.mime};base64,{encoded}"


def _no_image(name: str) -> ToolCallError:
    return ToolCallError(
        f'There is no image "{name}" to put in this page: use a name '
        "surfsense_list_images, surfsense_analyze_data or surfsense_make_image "
        "gave in this chat."
    )
