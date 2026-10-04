"""A PDF's pages for the agent: how many there are, and the first as PNG files it opens with `read`."""

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

# Enough to check a document's opening layout without filling the model's context.
PAGE_LIMIT = 4
# Wide enough to read body text, small enough to stay one image attachment.
PAGE_WIDTH_PX = 1000
# A taller page is drawn narrower: the bitmap is made in the API process, and a
# script may set any page size (ADR 0039).
PAGE_HEIGHT_PX = 4000
# A page this thin either way at the size it fits is a strip, not a page to check.
SHORTEST_SIDE_PX = 100

# pdfium is not thread-safe, and the API runs tools on a thread pool: every
# use of it in the API goes through this file.
_pdfium = threading.Lock()


@dataclass(frozen=True)
class DrawnPages:
    """The page images written, and a sentence naming each page left out."""

    pages: list[Path]
    skipped: list[str]


def page_count(pdf: bytes) -> int:
    """How many pages the PDF has.

    Raises pypdfium2.PdfiumError when the bytes are not a PDF.
    """
    with _pdfium:
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
    drawn = DrawnPages([], [])
    with _pdfium:
        document = pypdfium2.PdfDocument(pdf)
        try:
            for index in range(min(len(document), PAGE_LIMIT)):
                page = document[index]
                width, height = page.get_size()
                scale = min(PAGE_WIDTH_PX / width, PAGE_HEIGHT_PX / height)
                if min(width, height) * scale < SHORTEST_SIDE_PX:
                    drawn.skipped.append(
                        f"Page {index + 1} was not drawn: at {width:g} x "
                        f"{height:g} pt it is too long and thin to show."
                    )
                    continue
                path = folder / f"page-{index + 1}.png"
                page.render(scale=scale).to_pil().save(path, format="PNG")
                drawn.pages.append(path)
        finally:
            document.close()
    return drawn
