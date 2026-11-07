"""The PNG behind an image name a document script places: a source's figure, a chart its chat's analysis saved, or a picture its chat drew."""

from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.data_analysis.chart_names import chart_file, is_chart_name
from modules.artifacts.drawn_images.names import image_file, is_image_name
from modules.documents.source_figures import figure_file
from shared.config import get_storage_settings


def script_image_file(
    session: Session, workspace_id: int, thread_id: int | None, name: str
) -> Path:
    """LookupError when the workspace, or for a chart or picture the version's chat, holds none by that name."""
    charted, drawn = is_chart_name(name), is_image_name(name)
    if not charted and not drawn:
        return figure_file(session, workspace_id, name)
    if thread_id is None:
        raise LookupError(f"{name} is from a chat, and this document has no chat")
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    if drawn:
        return image_file(session, workspace_id, thread_id, folder, name)
    return chart_file(folder, name)
