"""A PDF's pages for the agent: how many there are, and the first as PNG files, shown inline and kept on disk for a closer look."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from shared import pdfium

# Enough to check a document's opening layout without filling the model's context.
PAGE_LIMIT = 4
# Wide enough to read body text; the result carries a smaller copy (inline_images).
PAGE_WIDTH_PX = 1000
# A taller page is drawn narrower: the bitmap is made in the API process, and a
# script may set any page size (ADR 0039).
PAGE_HEIGHT_PX = 4000
# A page this thin either way at the size it fits is a strip, not a page to check.
SHORTEST_SIDE_PX = 100


@dataclass(frozen=True)
class DrawnPages:
    """The page images written, and a sentence naming each page left out."""

    pages: list[Path]
    skipped: list[str]


def page_count(pdf: bytes) -> int:
    """How many pages the PDF has.

    Raises pypdfium2.PdfiumError when the bytes are not a PDF.
    """
    with pdfium.lock:
        document = pypdfium2.PdfDocument(pdf)
        try:
            return len(document)
        finally:
            document.close()


def draw_pages(pdf: bytes, folder: Path) -> DrawnPages:
    """Replace `folder` with `page-<k>.png` for each of the first pages.

    Raises pypdfium2.PdfiumError when the bytes are not a PDF.
    """
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    with pdfium.lock:
        document = pypdfium2.PdfDocument(pdf)
        try:
            wanted = [
                (index, index + 1, folder / f"page-{index + 1}.png")
                for index in range(min(len(document), PAGE_LIMIT))
            ]
            return _draw(document, wanted, PAGE_WIDTH_PX, PAGE_HEIGHT_PX)
        finally:
            document.close()


def draw_chosen_pages(
    pdf: bytes, wanted: list[tuple[int, int, Path]], long_side: int
) -> DrawnPages:
    """Draw each (index in the PDF, page number to name it by, path), at most
    `long_side` pixels either way.

    Raises pypdfium2.PdfiumError when the bytes are not a PDF.
    """
    with pdfium.lock:
        document = pypdfium2.PdfDocument(pdf)
        try:
            return _draw(document, wanted, long_side, long_side)
        finally:
            document.close()


def _draw(
    document: pypdfium2.PdfDocument,
    wanted: list[tuple[int, int, Path]],
    max_width: int,
    max_height: int,
) -> DrawnPages:
    """Called under the pdfium lock."""
    drawn = DrawnPages([], [])
    for index, number, path in wanted:
        page = document[index]
        width, height = page.get_size()
        # pdfium rounds pixels up, and 960 pt x (1000 / 960) is a hair over 1000.
        scale = min(max_width / width, max_height / height) * (1 - 1e-9)
        if min(width, height) * scale < SHORTEST_SIDE_PX:
            drawn.skipped.append(
                f"Page {number} was not drawn: at {width:g} x "
                f"{height:g} pt it is too long and thin to show."
            )
            continue
        page.render(scale=scale).to_pil().save(path, format="PNG")
        drawn.pages.append(path)
    return drawn
