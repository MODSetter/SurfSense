"""Pages of a source's own file drawn for the agent, so it can match the look the user means.

A PDF's pages are drawn here; a Word file or a deck is laid out by LibreOffice
when Office support is on, and otherwise printed by Electron from the
original, as the agent's own documents are. The source is only read.
"""

import time
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
from modules.agent.thread_folder.source_images import page_image_path
from modules.office_support import OfficeRunError, engine

# Big enough to read a heading's font and a table's lines. Shown inline (inline_images)
# and kept on disk for a closer look.
LONG_SIDE_PX = 1000
SNAPSHOT_SECONDS = 30
# A whole document's PDF; a warm conversion takes 1 to 5 s.
OFFICE_SECONDS = 60

# The suffixes with pages to draw, and what each calls its pages.
PAGED_SUFFIXES: dict[str, str] = {".pdf": "page", ".docx": "page", ".pptx": "slide"}


class PagesRefusedError(Exception):
    """Pages the source does not have, said with the ones it does."""


@dataclass(frozen=True)
class SourcePages:
    """How many pages the source has, the images drawn by page number, why any
    are missing, and the LibreOffice that laid them out, if one did."""

    count: str
    pages: list[tuple[int, Path]]
    reason: str | None = None
    drawn_by_office: str | None = None


def source_pages(
    folder: Path, document_id: int, original: Path, asked: list[int] | None
) -> SourcePages:
    """Draw the pages asked for, or the first ones, under the thread folder's `sources/pages/`.

    `asked` is sorted, without repeats, and at most PAGE_LIMIT long. Raises
    PagesRefusedError for a page the source is known not to have.
    """
    suffix = original.suffix.lower()
    unit = PAGED_SUFFIXES[suffix]
    if suffix == ".pdf":
        data = original.read_bytes()
        total = page_count(data)
        pages = _checked(asked, total, unit)
        return _drawn(folder, document_id, data, pages, _count(total, unit))
    slides = (slide_count(original) or 0) if suffix == ".pptx" else None
    if slides is not None:
        _checked(asked, slides, unit)
    laid_out = _laid_out_by_office(original, slides)
    if isinstance(laid_out, tuple):
        office, pdf = laid_out
        total = page_count(pdf)
        pages = _checked(asked, total, unit)
        drawn = _drawn(folder, document_id, pdf, pages, _count(total, unit))
        return SourcePages(drawn.count, drawn.pages, drawn.reason, office)
    if suffix == ".pptx":
        pages = _checked(asked, slides or 0, unit)
        printed = _printed(folder, document_id, original, "pptx", pages, slides)
    else:
        pages = asked or list(range(1, PAGE_LIMIT + 1))
        printed = _printed(folder, document_id, original, "docx", pages, None)
    if laid_out is None:
        return printed
    instead = "The desktop app printed these pages instead." if printed.pages else None
    reason = " ".join(filter(None, [laid_out, instead, printed.reason]))
    return SourcePages(printed.count, printed.pages, reason)


def _laid_out_by_office(
    original: Path, slides: int | None
) -> tuple[str, bytes] | str | None:
    """LibreOffice's name and its PDF of the whole file, why it failed, or None while Office support is off.

    A deck whose PDF leaves slides out (LibreOffice skips hidden ones) is
    printed by Electron instead, so slide numbers stay the deck's own.
    """
    office = engine.office_engine()
    if office is None:
        return None
    try:
        pdf = office.pdf_of(original, deadline=time.monotonic() + OFFICE_SECONDS)
        if slides is not None and page_count(pdf) != slides:
            return None
    except (OfficeRunError, pypdfium2.PdfiumError) as error:
        return str(error)
    return office.name, pdf


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
    folder: Path,
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
    return _drawn(folder, document_id, pdf, pages, count, in_order=True)


def _drawn(
    folder: Path,
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
            page_image_path(folder, document_id, page),
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
