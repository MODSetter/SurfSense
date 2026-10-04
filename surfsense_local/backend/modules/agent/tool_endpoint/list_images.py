"""The images tool: the figures SurfSense kept from the agent's sources, by the names scripts use."""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.sources_folder import SOURCES
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.documents.models import Document
from modules.documents.source_figures import (
    FiguresPending,
    SourceFigure,
    list_figures,
)

LISTING: dict[str, Any] = {
    "name": "list_images",
    "description": (
        "List the images SurfSense kept from sources: figures and charts from "
        "PDFs and Office files, and image files themselves. Each has the name to "
        "pass in surfsense_render_document's images, its size in pixels, and its "
        "page and caption when known."
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
    return "\n".join(
        [f'Source {source_id} ("{title}"):', *(_line(figure) for figure in figures)]
    )


def _line(figure: SourceFigure) -> str:
    """One image: its name, its size, then where it is and what it shows when known."""
    parts = [f"{figure.width}x{figure.height} px"]
    if figure.page is not None:
        parts.append(f"page {figure.page}")
    caption = _one_line(figure.caption or "")
    parts.append(f'caption "{caption}"' if caption else "no caption")
    return f"- {figure.name}: {', '.join(parts)}"


def _one_line(text: str) -> str:
    """A source's own text, kept on one line so it cannot pass for another entry."""
    return " ".join(text.split())


LIST_IMAGES = Tool(listing=LISTING, run=list_images)
