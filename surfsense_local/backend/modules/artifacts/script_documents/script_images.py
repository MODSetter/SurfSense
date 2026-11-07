"""The PNG behind an image name a document script places: a source's figure, a chart its chat's analysis saved, or a picture its chat drew."""

from collections.abc import Callable
from functools import partial
from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.data_analysis.chart_names import chart_file, is_chart_name
from modules.artifacts.drawn_images.names import (
    is_image_name,
    kept_picture,
    picture_png,
)
from modules.documents.source_figures import figure_file
from shared.config import get_storage_settings

# Called once the transaction has ended: a picture may be converted on the way.
ScriptImage = Callable[[], Path]


def script_image(
    session: Session, workspace_id: int, thread_id: int | None, name: str
) -> ScriptImage:
    """LookupError when the workspace, or for a chart or picture the version's chat, holds none by that name."""
    charted, drawn = is_chart_name(name), is_image_name(name)
    if not charted and not drawn:
        figure = figure_file(session, workspace_id, name)
        return lambda: figure
    if thread_id is None:
        raise LookupError(f"{name} is from a chat, and this document has no chat")
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    if drawn:
        picture = kept_picture(session, workspace_id, thread_id, name)
        return partial(picture_png, picture, folder)
    chart = chart_file(folder, name)
    return lambda: chart
