"""A scanned page read by OCR alone before Docling is asked.

Docling took 4.9 s and 39 CPU-s a page on the corpus's real scans; RapidOCR alone
about 2 s and 8 CPU-s, and found more of each page. A page whose OCR came out
garbled still goes to Docling, through the same splice a mixed PDF's flagged
pages take.
"""

import logging
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from sqlalchemy.orm import object_session

from modules.documents.models import Document
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.docling_batches.queue_turn import reading_turn
from worker.ingestion.figures.scanned_pages import scanned_pages
from worker.ingestion.pdf_reading.ocr_kept import (
    forget_reading,
    keep_reading,
    kept_reading,
)
from worker.ingestion.pdf_text_layer import LayerPage, TextLayer
from worker.ingestion.pdf_text_layer.page_triage import PageKind
from worker.ingestion.scan_ocr.frames import pdf_frames
from worker.ingestion.scan_ocr.page import KEPT, PageVerdict
from worker.ingestion.scan_ocr.reader import PageReader, page_reader
from worker.ingestion.scan_ocr.upright import read_upright
from worker.jobs import JobCancelledError, JobYieldedError

logger = logging.getLogger(__name__)

# Pages whose words only pixels hold: no text layer, a scanner's own OCR layer
# (re-read, as the text layer distrusts it), or text pdfium cannot map.
OCR_KINDS = frozenset({PageKind.NO_TEXT, PageKind.SCANNER_LAYER, PageKind.GARBLED})
# With no page of running text, a cover's title is all the layer has: the
# pixels of these pages hold the rest.
_PICTURE_KINDS = frozenset({PageKind.BIG_IMAGE, PageKind.SPARSE})
# Pages between checks for a cancel and for giving the queue up, as a Docling
# batch is 8 pages: some 17 s of RapidOCR's.
CHECK_EVERY = 8


@dataclass(frozen=True)
class OcrReading:
    """The layer with OCR's text on the pages it stands for, and why each page
    left for Docling went there."""

    layer: TextLayer
    docling: dict[int, str]
    read: int
    reader: str
    seconds: float
    # Pages kept from a run that gave the queue up, OCR's own or Docling's after it.
    kept: int = 0


def ocr_reading(
    original: Path, layer: TextLayer, document: Document | None = None
) -> OcrReading | None:
    """None when there is nothing for OCR here, no OCR on this computer, or it
    failed: Docling then reads as before. Raises JobYieldedError when a long
    reading gives the queue up with its pages kept, and JobCancelledError."""
    if not layer.pages:
        return None
    reader = page_reader()
    if reader is None:
        # Turned off since an earlier turn kept pages: Docling reads them all.
        forget_reading(original)
        return None
    try:
        candidates = _candidates(original, layer)
        if not candidates:
            return None
        return _read(reader, original, layer, candidates, document)
    except JobYieldedError:
        raise
    except JobCancelledError:
        # As a cancelled Docling reading drops its batches.
        forget_reading(original)
        raise
    except Exception:
        logger.warning(
            "%s could not read %s; Docling reads it",
            reader.name,
            original.name,
            exc_info=True,
        )
        # Docling reads every page, so the pages an earlier turn kept are no use.
        forget_reading(original)
        return None


def _candidates(original: Path, layer: TextLayer) -> list[int]:
    pages = list(enumerate(layer.pages, start=1))
    picked = {n for n, page in pages if page.text is None and page.kind in OCR_KINDS}
    turned = [n for n, page in pages if page.text is None and page.kind is None]
    if turned:
        # A turned page is OCR's only when it is a scan; pdfium renders it upright.
        scans = scanned_pages(original) or []
        picked |= {n for n in turned if n <= len(scans) and scans[n - 1]}
    if not any(
        page.kind is PageKind.TEXT for _, page in pages if page.text is not None
    ):
        picked |= {n for n, page in pages if page.kind in _PICTURE_KINDS}
    return sorted(picked)


@dataclass
class _Pages:
    """OCR's pages so far: each page's text, why the others go to Docling, and
    which read as text."""

    texts: dict[int, str] = field(default_factory=dict)
    docling: dict[int, str] = field(default_factory=dict)
    stood: set[int] = field(default_factory=set)

    @classmethod
    def kept(cls, kept: dict[str, Any] | None, candidates: list[int]) -> "_Pages":
        """What an earlier run kept, of the pages OCR reads now."""
        if kept is None:
            return cls()
        wanted = set(candidates)
        return cls(
            {int(n): text for n, text in kept["texts"].items() if int(n) in wanted},
            {int(n): why for n, why in kept["docling"].items() if int(n) in wanted},
            {int(n) for n in kept["stood"] if int(n) in wanted},
        )

    def __contains__(self, n: int) -> bool:
        return n in self.texts or n in self.docling

    def to_keep(self) -> dict[str, Any]:
        return {
            "texts": self.texts,
            "docling": self.docling,
            "stood": sorted(self.stood),
        }


def _read(
    reader: PageReader,
    original: Path,
    layer: TextLayer,
    candidates: list[int],
    document: Document | None,
) -> OcrReading | None:
    started = time.perf_counter()
    read = _Pages.kept(kept_reading(original, reader.name), candidates)
    kept = len(read.texts) + len(read.docling)
    left = [n for n in candidates if n not in read]
    if left:
        _ocr(reader, original, layer, left, document, read)
    if not read.stood:
        # No page read as text: Docling reads the file whole, as before.
        forget_reading(original)
        return None
    if left and read.docling:
        # For the run that resumes should Docling's part give the queue up.
        keep_reading(original, reader.name, read.to_keep())
    docling = dict(read.docling)
    pages: list[LayerPage] = list(layer.pages)
    for n, text in read.texts.items():
        pages[n - 1] = replace(pages[n - 1], text=text, refused_because=None)
    for n, page in enumerate(pages, start=1):
        if page.text is None and n not in docling:
            docling[n] = page.refused_because or f"page {n} is for Docling"
    return OcrReading(
        replace(layer, pages=tuple(pages)),
        docling,
        len(read.texts),
        reader.name,
        time.perf_counter() - started,
        kept=kept,
    )


def _ocr(
    reader: PageReader,
    original: Path,
    layer: TextLayer,
    left: list[int],
    document: Document | None,
    read: _Pages,
) -> None:
    """Reads the pages `left` into `read`."""
    # The ingest job's own session; a reading outside one has nothing to check.
    session = object_session(document) if document is not None else None
    turn = reading_turn(session, document) if session and document else None
    # Closed here, whatever stops the reading: its PDF closes under pdfium's lock,
    # which the garbage collector could otherwise take while this thread holds it.
    with closing(pdf_frames(original, left, reader.max_side)) as frames:
        for count, (frame, page) in enumerate(read_upright(reader, frames), start=1):
            n, verdict = frame.number, page.verdict()
            if verdict not in KEPT:
                read.docling[n] = f"page {n} is {verdict}"
            elif verdict is PageVerdict.TEXT:
                read.texts[n] = page.text()
                read.stood.add(n)
            else:
                # Little or nothing read: a cover's own title, if it has one, wins.
                read.texts[n] = layer.pages[n - 1].text or page.text()
            if turn is not None and count % CHECK_EVERY == 0:
                turn.check_cancelled()
                if count < len(left):
                    _give_way(
                        turn,
                        lambda: keep_reading(original, reader.name, read.to_keep()),
                    )


def _give_way(turn: QueueTurn, keep: Callable[[], bool]) -> None:
    """Gives the queue up only with OCR's pages kept, so the run that resumes
    reads none of them again."""
    try:
        turn.give_way()
    except JobYieldedError:
        if keep():
            raise
