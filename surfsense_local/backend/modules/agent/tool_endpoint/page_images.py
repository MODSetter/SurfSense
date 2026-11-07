"""The images a page names, made inline as it is kept.

The agent has no shell to encode a picture, and typing base64 through a model is
not practical; the viewer gives a page no network, so a data URL is the only way in.
"""

import base64
import re

from sqlalchemy.orm import Session

from modules.agent.previews.inline_images import inline_image
from modules.agent.tool_endpoint.selected_images import refuse_unselected_images
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.drawn_images.names import ImageStillDrawingError
from modules.artifacts.script_documents.script_images import script_image_file

PREFIX = "surfsense-image:"
_PLACED = re.compile(re.escape(PREFIX) + r"([A-Za-z0-9_-]+)")


def with_placed_images(session: Session, scope: TurnScope, page: str) -> str:
    """The page with each named image as a data URL; the refusal if one cannot be had."""
    names = list(dict.fromkeys(_PLACED.findall(page)))
    if not names:
        return page
    refuse_unselected_images(scope, names)
    try:
        urls = {name: _data_url(session, scope, name) for name in names}
    finally:
        session.rollback()  # reads only; the version is made in its own transaction
    return _PLACED.sub(lambda placed: urls[placed[1]], page)


def _data_url(session: Session, scope: TurnScope, name: str) -> str:
    thread_id = scope.thread_id if scope.known else None
    try:
        path = script_image_file(session, scope.workspace_id, thread_id, name)
        # Scaled as a tool result's image is, so a page holds many within its limit.
        image = inline_image(path)
    except ImageStillDrawingError as error:
        raise ToolCallError(
            f'The picture "{name}" is still being drawn. Tell the user the page can '
            "use it once it appears in Studio, and stop."
        ) from error
    except (LookupError, OSError, ValueError) as error:
        raise ToolCallError(
            f'There is no image "{name}" to put in this page: use a name '
            "surfsense_list_images, surfsense_analyze_data or surfsense_make_image "
            "gave in this chat."
        ) from error
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime};base64,{encoded}"
