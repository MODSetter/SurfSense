"""The images tool: the figures SurfSense kept from the agent's sources, by the names scripts use."""

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.sources_folder import FIGURES, SOURCES, show_figure
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.documents.models import Document
from modules.documents.source_figures import (
    FiguresPending,
    SourceFigure,
    figure_file,
    list_figures,
)

LISTING: dict[str, Any] = {
    "name": "list_images",
    "description": (
        "List the images SurfSense kept from sources: figures and charts from "
        "PDFs and Office files, and image files themselves. Each has the name to "
        "pass in surfsense_render_document's images, its size in pixels, its "
        "page and caption when known, and a copy under "
        f"{SOURCES}/{FIGURES}/ to open with read, for example to read a chart's "
        "values. If read cannot show it to you, place the image with its caption "
        "rather than guess what it shows."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "The sources to look in: the number in brackets at the end of "
                    f"each file name in {SOURCES}/."
                ),
            }
        },
        "required": ["source_ids"],
    },
}


def list_images(session: Session, workspace_id: int, arguments: dict[str, Any]) -> str:
    """Each named source's images, or why it has none to give yet."""
    source_ids = arguments.get("source_ids")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or not all(
            isinstance(source_id, int) and not isinstance(source_id, bool)
            for source_id in source_ids
        )
    ):
        raise ToolCallError(
            "Name at least one source: the number in brackets at the end of its "
            f"file name in {SOURCES}/."
        )
    return "\n\n".join(
        _source_images(session, workspace_id, source_id)
        for source_id in dict.fromkeys(source_ids)
    )


def _source_images(session: Session, workspace_id: int, source_id: int) -> str:
    try:
        figures = list_figures(session, workspace_id, source_id)
    except FiguresPending:
        return (
            f"Source {source_id}: its images are being extracted. Ask again in a "
            "minute."
        )
    except LookupError:
        return f"Source {source_id}: not a source in this workspace."
    title = _one_line(session.get(Document, source_id).title)
    if not figures:
        return f'Source {source_id} ("{title}"): no images.'
    lines = [
        _line(figure, show_figure(workspace_id, figure.name, png))
        for figure in figures
        if (png := _kept_png(session, workspace_id, figure)) is not None
    ]
    return "\n".join([f'Source {source_id} ("{title}"):', *lines])


def _kept_png(session: Session, workspace_id: int, figure: SourceFigure) -> Path | None:
    """The figure's file; None when it left the disk after it was listed."""
    try:
        return figure_file(session, workspace_id, figure.name)
    except LookupError:
        return None


def _line(figure: SourceFigure, shown_at: str) -> str:
    """One image: its name, its size, where it is and what it shows when known, and its copy."""
    parts = [f"{figure.width}x{figure.height} px"]
    if figure.page is not None:
        parts.append(f"page {figure.page}")
    caption = _one_line(figure.caption or "")
    parts.append(f'caption "{caption}"' if caption else "no caption")
    parts.append(f"at {shown_at}")
    return f"- {figure.name}: {', '.join(parts)}"


def _one_line(text: str) -> str:
    """A source's own text, kept on one line so it cannot pass for another entry."""
    return " ".join(text.split())


LIST_IMAGES = Tool(listing=LISTING, run=list_images)
