"""The source pages tool: a source's own pages as images, to see the look the user means."""

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.previews.page_images import PAGE_LIMIT
from modules.agent.previews.source_pages import (
    LONG_SIDE_PX,
    PAGED_SUFFIXES,
    PagesRefusedError,
    SourcePages,
    source_pages,
)
from modules.agent.thread_folder.layout import PAGES, SOURCES
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# The snapshot page lays Word out with docx-preview, told to skip both.
_WORD_PAGES = (
    "Word pages are laid out as SurfSense's viewer lays them out, without headers "
    "and footers, which can differ a little from Word."
)

LISTING: dict[str, Any] = {
    "name": "source_pages",
    "description": (
        f"Draw up to {PAGE_LIMIT} pages of a PDF, Word or PowerPoint source as "
        f"images under {SOURCES}/{PAGES}/, to see its look: fonts, colours, "
        "layout. Returns how many pages it has and the images to open with read."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "integer",
                "description": (
                    "The source: the number in brackets at the end of its file "
                    f"name in {SOURCES}/."
                ),
            },
            "pages": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    f"Page or slide numbers from 1, at most {PAGE_LIMIT}. Leave out "
                    "for the first pages."
                ),
            },
        },
        "required": ["document_id"],
    },
}


def draw(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    """The pages drawn, how many the source has, and why any are missing; the source is only read."""
    document_id = arguments.get("document_id")
    if not isinstance(document_id, int) or isinstance(document_id, bool):
        raise ToolCallError(
            "Give the document_id: the number in brackets at the end of a source's "
            f"file name in {SOURCES}/."
        )
    asked = _asked(arguments.get("pages"))
    scope.refuse_unselected([document_id])
    title, original = _paged_original(session, scope.workspace_id, document_id)
    # Drawing a Word file or a deck waits on Electron; no transaction may stay open.
    session.commit()
    try:
        drawn = source_pages(scope.folder, document_id, original, asked)
    except PagesRefusedError as refused:
        raise ToolCallError(f'Source {document_id} ("{title}") {refused}') from refused
    return _shown(scope.folder, document_id, title, original, drawn)


def _asked(pages: object) -> list[int] | None:
    """The page numbers asked for, in order, without repeats; None for the first pages."""
    if pages is None:
        return None
    if (
        not isinstance(pages, list)
        or not pages
        or not all(
            isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in pages
        )
    ):
        raise ToolCallError(
            "pages must be a list of page numbers from 1, or left out for the first "
            "pages."
        )
    unique = sorted(set(pages))
    if len(unique) > PAGE_LIMIT:
        raise ToolCallError(f"Ask for at most {PAGE_LIMIT} pages at a time.")
    return unique


def _paged_original(
    session: Session, workspace_id: int, document_id: int
) -> tuple[str, Path]:
    """The source's title and its original file, refused when it has no pages to draw."""
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise ToolCallError(f"Source {document_id}: not a source in this workspace.")
    title = " ".join(document.title.split())
    path = (
        original_path(document) if document.document_type is DocumentType.FILE else None
    )
    if path is None:
        raise ToolCallError(
            f'Source {document_id} ("{title}") has no file of its own to draw: '
            f"read its text in {SOURCES}/ instead."
        )
    suffix = path.suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        raise ToolCallError(
            f'Source {document_id} ("{title}") is an image: find it with '
            "surfsense_list_images and open its copy with read."
        )
    if suffix not in PAGED_SUFFIXES:
        raise ToolCallError(
            f'Source {document_id} ("{title}") is not a PDF, Word or PowerPoint '
            f"file, so it has no pages to draw: read its text in {SOURCES}/ instead."
        )
    return title, path


def _shown(
    folder: Path, document_id: int, title: str, original: Path, drawn: SourcePages
) -> str:
    unit = PAGED_SUFFIXES[original.suffix.lower()]
    lines = [f'Source {document_id} ("{title}") has {drawn.count}.']
    if drawn.pages:
        lines.append(
            f"{unit.capitalize()}s to open with read, at most {LONG_SIDE_PX} px on "
            "their long side:"
        )
        lines += [f"- {path.relative_to(folder).as_posix()}" for _, path in drawn.pages]
        if drawn.reason:
            lines.append(drawn.reason)
    else:
        lines.append(f"No pages were drawn: {drawn.reason or 'none were drawn.'}")
    if original.suffix.lower() == ".docx":
        lines.append(_WORD_PAGES)
    return "\n".join(lines)


# Offered only to a model that reads images: to any other, each page is an error.
SOURCE_PAGES = Tool(listing=LISTING, run=draw, waits=True, needs_image_input=True)
