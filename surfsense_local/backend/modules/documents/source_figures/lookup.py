from pathlib import Path

from sqlalchemy.orm import Session

from modules.documents.source_figures.figure import parse_figure_name
from modules.documents.source_figures.layout import figure_png, read_index
from modules.documents.source_figures.source import (
    kept_figures_dir,
    source_in_workspace,
)


def figure_file(session: Session, workspace_id: int, name: str) -> Path:
    """The PNG a figure name stands for, if this workspace holds it and it is on disk."""
    parsed = parse_figure_name(name)
    if parsed is None:
        raise LookupError(f"{name!r} is not a figure name")
    document_id, n = parsed

    folder = kept_figures_dir(source_in_workspace(session, workspace_id, document_id))
    listed = any(entry["n"] == n for entry in read_index(folder) or [])
    path = figure_png(folder, n)
    if not listed or not path.is_file():
        raise LookupError(f"no figure {name} in this workspace")
    return path
