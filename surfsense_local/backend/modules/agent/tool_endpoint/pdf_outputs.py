"""What a PDF tool made, kept as new artifacts in Studio, and its pages shown to the model.

The first line of a one-artifact result is `Made artifact <id>: <title>`.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.previews.inline_images import inline_image
from modules.agent.previews.page_images import PAGE_LIMIT, draw_chosen_pages
from modules.agent.thread_folder.layout import OUTPUTS, PREVIEWS
from modules.agent.thread_folder.path_budget import TOO_DEEP, fits
from modules.agent.tool_endpoint.pdf_inputs import PdfInput
from modules.agent.tool_endpoint.tool import InlineImage, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.made_file import (
    TITLE_CHARS,
    MadeFileRefusedError,
    keep_made_file,
)
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

# The size source pages are kept at for a closer look.
PREVIEW_LONG_SIDE = 1000
NO_IMAGES = "No page previews: the selected model cannot read images."


@dataclass(frozen=True)
class MadePdf:
    """One new PDF: its title, bytes, page count, and the pages worth showing, from 1."""

    title: str
    data: bytes
    page_count: int
    shown: list[int]


@dataclass(frozen=True)
class _Kept:
    artifact_id: int
    made: MadePdf


def derived_title(title: object, base: str, suffix: str) -> str:
    """The title asked for, else the input's with what was done to it, cut to fit."""
    if title is not None and not isinstance(title, str):
        raise ToolCallError("title must be text, or left out.")
    if isinstance(title, str) and title.strip():
        return title
    room = TITLE_CHARS - len(suffix) - 3
    return f"{base[:room].rstrip()} ({suffix})"


def keep(
    session: Session,
    scope: TurnScope,
    inputs: list[PdfInput],
    made: list[MadePdf],
    made_by: dict[str, Any],
    notes: tuple[str, ...] = (),
) -> str | ToolResult:
    """Each new PDF as an artifact derived from `inputs`, then what the model reads about them."""
    kept: list[_Kept] = []
    for pdf in made:
        try:
            artifact = keep_made_file(
                session,
                scope.workspace_id,
                title=pdf.title,
                format="pdf",
                data=pdf.data,
                made_by=made_by,
                document_ids=[i.document_id for i in inputs if i.document_id],
                artifact_ids=[i.artifact_id for i in inputs if i.artifact_id],
                chat_thread_id=scope.thread_id if scope.known else None,
            )
        except MadeFileRefusedError as refused:
            session.rollback()
            raise ToolCallError(str(refused)) from refused
        kept.append(_Kept(artifact.id, pdf))
    text, images = _shown(scope.folder, kept)
    body = "\n".join([*_described(kept, inputs), *notes, *text, _onward(kept)])
    return ToolResult(body, tuple(images)) if images else body


def _described(kept: list[_Kept], inputs: list[PdfInput]) -> list[str]:
    sources = _listed([pdf.mention for pdf in inputs])
    unchanged = "It is unchanged." if len(inputs) == 1 else "They are unchanged."
    if len(kept) == 1:
        (one,) = kept
        return [
            f"Made artifact {one.artifact_id}: {' '.join(one.made.title.split())}",
            f"A new PDF of {_pages(one.made.page_count)} in Studio, made from "
            f"{sources}. {unchanged}",
        ]
    return [
        f"Made {len(kept)} artifacts, each a new PDF in Studio, from {sources}. "
        f"{unchanged}",
        *(
            f"- artifact {k.artifact_id}: {k.made.title}, {_pages(k.made.page_count)}"
            for k in kept
        ),
    ]


def _onward(kept: list[_Kept]) -> str:
    if len(kept) == 1:
        return (
            f"To work on it further, pass artifact_id {kept[0].artifact_id} to a "
            "PDF tool."
        )
    return "To work on one further, pass its artifact_id to a PDF tool."


def _shown(folder: Path, kept: list[_Kept]) -> tuple[list[str], list[InlineImage]]:
    """The previews as images, and the lines that say which pages they are."""
    if not declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE):
        return [NO_IMAGES], []
    if len(kept) == 1:
        made = kept[0].made
        pages = [page for page in made.shown if 1 <= page <= made.page_count]
        wanted = [(kept[0], page) for page in pages[:PAGE_LIMIT]]
    else:
        wanted = [(k, 1) for k in kept[:PAGE_LIMIT]]
    paths = [
        folder / OUTPUTS / PREVIEWS / str(one.artifact_id) / f"page-{page}.png"
        for one, page in wanted
    ]
    if not all(fits(path) for path in paths):
        return [f"No page previews: {TOO_DEEP.format(what='page previews')}"], []
    # A new artifact's id may be a deleted one's, whose pages are still there.
    for parent in dict.fromkeys(path.parent for path in paths):
        shutil.rmtree(parent, ignore_errors=True)
        parent.mkdir(parents=True)
    images: list[InlineImage] = []
    lines: list[str] = []
    shown: list[str] = []
    for (one, page), path in zip(wanted, paths, strict=True):
        try:
            drawn = _draw(one, page, path)
            if drawn is None:
                lines.append(
                    f"Page {page} was not drawn: it is too long and thin to show."
                )
                continue
            images.append(inline_image(drawn))
        # A page that will not draw or encode costs that page, never the made PDF.
        except Exception:
            logger.exception("page %s of artifact %s not shown", page, one.artifact_id)
            lines.append(
                f"Page {page} of artifact {one.artifact_id} could not be shown."
            )
            continue
        shown.append(str(page if len(kept) == 1 else one.artifact_id))
    if not images:
        return ["No page previews: none could be drawn.", *lines], []
    if len(kept) > 1:
        heading = (
            "The first page of each comes with this result as an image, in order: "
            f"artifact{'' if len(shown) == 1 else 's'} {_listed(shown)}."
        )
    elif len(shown) == 1:
        heading = f"Page {shown[0]} comes with this result as an image."
    else:
        heading = f"Pages {_listed(shown)} come with this result as images, in order."
    kept_in = f"{OUTPUTS}/{PREVIEWS}/"
    where = (
        f"{kept_in}{kept[0].artifact_id}/"
        if len(kept) == 1
        else f"{kept_in}<artifact id>/"
    )
    return [
        heading,
        f"Look at {'it' if len(images) == 1 else 'them'} before you answer.",
        *lines,
        f"Larger copies are in {where} as page-<n>.png; open one with read only "
        "for a closer look.",
    ], images


def _draw(one: _Kept, page: int, path: Path) -> Path | None:
    """The page drawn at most PREVIEW_LONG_SIDE pixels either way; None when too thin."""
    drawn = draw_chosen_pages(
        one.made.data, [(page - 1, page, path)], PREVIEW_LONG_SIDE
    )
    return drawn.pages[0] if drawn.pages else None


def _pages(count: int) -> str:
    return f"{count:,} page" if count == 1 else f"{count:,} pages"


def _listed(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"
