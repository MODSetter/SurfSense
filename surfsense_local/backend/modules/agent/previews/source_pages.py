"""Pages of a source's own file drawn for the agent, so it can match the look the user means.

A PDF's pages are drawn here; a Word file or a deck is printed by Electron
from the original, as the agent's own documents are. The source is only read.
"""

from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from modules.agent.previews import docx_snapshots
from modules.agent.previews.office_counts import slide_count, word_saved_pages
from modules.agent.previews.page_images import (
    PAGE_LIMIT,
    draw_chosen_pages,
    page_count,
)
from modules.agent.sources_folder import page_image_path

# Big enough to read a heading's font and a table's lines, small enough for one attachment.
LONG_SIDE_PX = 1000
SNAPSHOT_SECONDS = 30

# The suffixes with pages to draw, and what each calls its pages.
PAGED_SUFFIXES: dict[str, str] = {".pdf": "page", ".docx": "page", ".pptx": "slide"}


class PagesRefusedError(Exception):
    """Pages the source does not have, said with the ones it does."""


@dataclass(frozen=True)
class SourcePages:
    """How many pages the source has, the images drawn by page number, and why any are missing."""

    count: str
    pages: list[tuple[int, Path]]
    reason: str | None = None


def source_pages(
    workspace_id: int, document_id: int, original: Path, asked: list[int] | None
) -> SourcePages:
    """Draw the pages asked for, or the first ones, under `sources/pages/`.

    `asked` is sorted, without repeats, and at most PAGE_LIMIT long. Raises
    PagesRefusedError for a page the source is known not to have.
    """
    suffix = original.suffix.lower()
    unit = PAGED_SUFFIXES[suffix]
    if suffix == ".pdf":
        data = original.read_bytes()
        total = page_count(data)
        pages = _checked(asked, total, unit)
        return _drawn(workspace_id, document_id, data, pages, _count(total, unit))
    if suffix == ".pptx":
        total = slide_count(original) or 0
        pages = _checked(asked, total, unit)
        return _printed(workspace_id, document_id, original, "pptx", pages, total)
    pages = asked or list(range(1, PAGE_LIMIT + 1))
    return _printed(workspace_id, document_id, original, "docx", pages, None)


def _checked(asked: list[int] | None, total: int, unit: str) -> list[int]:
    if total == 0:
        raise PagesRefusedError(f"has no {unit}s to draw.")
    if asked is None:
        return list(range(1, min(total, PAGE_LIMIT) + 1))
    if asked[-1] > total:
        raise PagesRefusedError(
            f"has {_count(total, unit)}: ask for {unit}s from 1 to {total}."
        )
    return asked


def _printed(
    workspace_id: int,
    document_id: int,
    original: Path,
    format: docx_snapshots.SnapshotFormat,
    pages: list[int],
    total: int | None,
) -> SourcePages:
    """Electron prints exactly those pages, in order; a Word file's count shows only when a print comes up short."""
    unit = "slide" if format == "pptx" else "page"
    try:
        pdf = docx_snapshots.snapshots.snapshot(
            format=format,
            source_file=original,
            pages=_page_ranges(pages),
            timeout=SNAPSHOT_SECONDS,
        )
        printed = page_count(pdf)
    except (docx_snapshots.SnapshotUnavailableError, pypdfium2.PdfiumError) as error:
        return SourcePages(_count_line(original, total, unit, None), [], str(error))
    if 0 < printed < len(pages) and _contiguous(pages) and total is None:
        # Printing stops at the document's end: the last page printed is its last.
        total = pages[0] - 1 + printed
        pages = pages[:printed]
    if printed == 0 or printed != len(pages):
        return SourcePages(
            _count_line(original, total, unit, None),
            [],
            f"the desktop app printed {printed} {unit}s for the {len(pages)} asked for.",
        )
    count = _count_line(original, total, unit, pages[-1])
    return _drawn(workspace_id, document_id, pdf, pages, count, in_order=True)


def _drawn(
    workspace_id: int,
    document_id: int,
    pdf: bytes,
    pages: list[int],
    count: str,
    *,
    in_order: bool = False,
) -> SourcePages:
    """Draw from the source's own PDF by page number, or from a print holding just those pages."""
    wanted = [
        (
            position if in_order else page - 1,
            page,
            page_image_path(workspace_id, document_id, page),
        )
        for position, page in enumerate(pages)
    ]
    try:
        drawn = draw_chosen_pages(pdf, wanted, LONG_SIDE_PX)
    except pypdfium2.PdfiumError as error:
        return SourcePages(count, [], f"the pages could not be drawn: {error}")
    numbers = {path: page for _, page, path in wanted}
    return SourcePages(
        count,
        [(numbers[path], path) for path in drawn.pages],
        " ".join(drawn.skipped) or None,
    )


def _count_line(
    original: Path, total: int | None, unit: str, last_drawn: int | None
) -> str:
    """The count when known; for Word, what Word saved, else at least the pages printed."""
    if total is not None:
        return _count(total, unit)
    saved = word_saved_pages(original)
    if saved is not None:
        return f"{_count(saved, unit)}, as Word last counted them"
    if last_drawn is not None:
        return f"at least {_count(last_drawn, unit)}"
    return "an unknown number of pages"


def _page_ranges(pages: list[int]) -> str:
    """printToPDF's pageRanges: a run of pages as a range, others by number."""
    if _contiguous(pages) and len(pages) > 1:
        return f"{pages[0]}-{pages[-1]}"
    return ",".join(map(str, pages))


def _contiguous(pages: list[int]) -> bool:
    return pages == list(range(pages[0], pages[0] + len(pages)))


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
