"""The images tool: the figures SurfSense kept from the agent's sources, by the names scripts use."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import FIGURES, SOURCES
from modules.agent.thread_folder.source_images import PathTooLongError, show_figure
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.documents.models import Document
from modules.documents.source_figures import (
    FiguresPending,
    SourceFigure,
    list_figures,
    parse_figure_name,
)
from modules.documents.source_figures.layout import figure_png
from modules.documents.source_figures.source import kept_figures_dir

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


def list_images(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
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
    scope.refuse_unselected(source_ids)
    workspace_id = scope.workspace_id
    listed = [
        _source_images(session, workspace_id, source_id)
        for source_id in dict.fromkeys(source_ids)
    ]
    # Copying grows with the number of figures; the write lock must not be held across it.
    session.commit()
    return "\n\n".join(_shown(scope.folder, source) for source in listed)


@dataclass(frozen=True)
class _SourceImages:
    """One source's heading, or the whole answer when it has no images to give."""

    text: str
    figures: list[tuple[SourceFigure, Path]] = field(default_factory=list)


def _source_images(
    session: Session, workspace_id: int, source_id: int
) -> _SourceImages:
    try:
        figures = list_figures(session, workspace_id, source_id)
    except FiguresPending:
        return _SourceImages(
            f"Source {source_id}: its images are being extracted. Ask again in a "
            "minute."
        )
    except LookupError:
        return _SourceImages(f"Source {source_id}: not a source in this workspace.")
    document = session.get(Document, source_id)
    title = _one_line(document.title)
    if not figures:
        return _SourceImages(f'Source {source_id} ("{title}"): no images.')
    # list_figures read the index once; each listed figure's PNG sits beside it.
    folder = kept_figures_dir(document)
    return _SourceImages(
        f'Source {source_id} ("{title}"):',
        [(figure, figure_png(folder, _number(figure))) for figure in figures],
    )


def _shown(folder: Path, source: _SourceImages) -> str:
    """The source's lines, each figure copied where `read` opens it; one gone from disk is left out."""
    lines = [
        _line(figure, _copied(folder, figure, png))
        for figure, png in source.figures
        if png.is_file()
    ]
    return "\n".join([source.text, *lines])


def _copied(folder: Path, figure: SourceFigure, png: Path) -> str:
    """Where its copy to open is; without one, its name still places it in a script."""
    try:
        return f"at {show_figure(folder, figure.name, png)}"
    except PathTooLongError as too_long:
        return f"no copy to open: {too_long}"


def _number(figure: SourceFigure) -> int:
    parsed = parse_figure_name(figure.name)
    assert parsed is not None  # list_figures names every figure it lists
    return parsed[1]


def _line(figure: SourceFigure, shown_at: str) -> str:
    """One image: its name, its size, where it is and what it shows when known, and its copy."""
    parts = [f"{figure.width}x{figure.height} px"]
    if figure.page is not None:
        parts.append(f"page {figure.page}")
    caption = _one_line(figure.caption or "")
    parts.append(f'caption "{caption}"' if caption else "no caption")
    parts.append(shown_at)
    return f"- {figure.name}: {', '.join(parts)}"


def _one_line(text: str) -> str:
    """A source's own text, kept on one line so it cannot pass for another entry."""
    return " ".join(text.split())


LIST_IMAGES = Tool(listing=LISTING, run=list_images, waits=True)
