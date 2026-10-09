"""The PNG behind an image name a document script places: a source's figure, or a chart its chat's analysis saved."""

from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.data_analysis.chart_names import chart_file, is_chart_name
from modules.documents.source_figures import figure_file
from shared.config import get_storage_settings


def script_image_file(
    session: Session, workspace_id: int, thread_id: int | None, name: str
) -> Path:
    """LookupError when the workspace, or for a chart the version's chat, holds none by that name."""
    if not is_chart_name(name):
        return figure_file(session, workspace_id, name)
    if thread_id is None:
        raise LookupError(f"{name} is a chart, and this document has no chat")
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    return chart_file(folder, name)
