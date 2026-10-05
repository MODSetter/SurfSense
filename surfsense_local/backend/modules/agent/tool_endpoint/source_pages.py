"""The source pages tool: a source's own pages as images, to see the look the user means."""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.previews.inline_images import inline_image
from modules.agent.previews.page_images import PAGE_LIMIT
from modules.agent.previews.source_pages import (
    PAGED_SUFFIXES,
    PagesRefusedError,
    SourcePages,
    source_pages,
)
from modules.agent.sources_folder import PAGES, SOURCES
from modules.agent.tool_endpoint.tool import (
    InlineImage,
    Tool,
    ToolCallError,
    ToolResult,
)
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# The snapshot page lays Word out with docx-preview, told to skip both.
_WORD_PAGES = (
    "Word pages are laid out as SurfSense's viewer lays them out, without headers "
    "and footers, which can differ a little from Word."
)

LISTING: dict[str, Any] = {
    "name": "source_pages",
    "description": (
        f"Draw up to {PAGE_LIMIT} pages of a PDF, Word or PowerPoint source and "
        "return them as images, to see its look: fonts, colours, layout. Copies "
        f"are kept under {SOURCES}/{PAGES}/."
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


def draw(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """The pages drawn as images, how many the source has, and why any are missing; the source is only read."""
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
        drawn = source_pages(scope.workspace_id, document_id, original, asked)
    except PagesRefusedError as refused:
        raise ToolCallError(f'Source {document_id} ("{title}") {refused}') from refused
    return _shown(scope.workspace_id, document_id, title, original, drawn)


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
    workspace_id: int, document_id: int, title: str, original: Path, drawn: SourcePages
) -> str | ToolResult:
    """The pages as images in ascending order; a page that will not encode is named instead."""
    folder = get_storage_settings().agent_working_dir(workspace_id)
    unit = PAGED_SUFFIXES[original.suffix.lower()]
    lines = [f'Source {document_id} ("{title}") has {drawn.count}.']
    shown: list[int] = []
    images: list[InlineImage] = []
    unattached: list[str] = []
    for number, path in drawn.pages:
        try:
            images.append(inline_image(path))
        # A page that will not encode costs that page, not the others drawn.
        except Exception:
            logger.exception(
                "%s %s of source %s not attached", unit, number, document_id
            )
            unattached.append(
                f"{unit.capitalize()} {number} could not be attached; open "
                f"{path.relative_to(folder).as_posix()} with read."
            )
            continue
        shown.append(number)
    if shown:
        lines.append(_come_with(unit, shown))
    elif drawn.pages:
        lines.append(f"No {unit}s could be attached.")
    else:
        lines.append(f"No pages were drawn: {drawn.reason or 'none were drawn.'}")
    if drawn.pages and drawn.reason:
        lines.append(drawn.reason)
    lines += unattached
    if shown:
        lines.append(
            f"Larger copies are in {SOURCES}/{PAGES}/ as {document_id}-p<n>.png; "
            "open one with read only for a closer look."
        )
    if original.suffix.lower() == ".docx":
        lines.append(_WORD_PAGES)
    text = "\n".join(lines)
    return ToolResult(text, tuple(images)) if images else text


def _come_with(unit: str, numbers: list[int]) -> str:
    """Which pages the images after the text are, as one sentence."""
    if len(numbers) == 1:
        return f"{unit.capitalize()} {numbers[0]} comes with this result as an image."
    listed = ", ".join(map(str, numbers[:-1])) + f" and {numbers[-1]}"
    return f"{unit.capitalize()}s {listed} come with this result as images, in order."


# Offered only to a model that reads images: to any other, each page is an error.
SOURCE_PAGES = Tool(listing=LISTING, run=draw, waits=True, needs_image_input=True)
