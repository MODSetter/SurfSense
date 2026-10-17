"""A scanned page read by OCR alone before Docling is asked.

Docling took 4.9 s and 39 CPU-s a page on the corpus's real scans; RapidOCR alone
about 2 s and 8 CPU-s, and found more of each page. A page whose OCR came out
garbled still goes to Docling, through the same splice a mixed PDF's flagged
pages take.
"""

import logging
import time
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy.orm import object_session

from modules.documents.models import Document
from worker.ingestion.docling_batches.queue_turn import reading_turn
from worker.ingestion.figures.scanned_pages import scanned_pages
from worker.ingestion.pdf_reading.ocr_kept import keep_reading, kept_reading
from worker.ingestion.pdf_text_layer import LayerPage, TextLayer
from worker.ingestion.pdf_text_layer.page_triage import PageKind
from worker.ingestion.scan_ocr.frames import pdf_frames
from worker.ingestion.scan_ocr.page import KEPT, PageVerdict
from worker.ingestion.scan_ocr.reader import PageReader, page_reader
from worker.ingestion.scan_ocr.upright import read_upright
from worker.jobs import JobCancelledError

logger = logging.getLogger(__name__)

# Pages whose words only pixels hold: no text layer, a scanner's own OCR layer
# (re-read, as the text layer distrusts it), or text pdfium cannot map.
OCR_KINDS = frozenset({PageKind.NO_TEXT, PageKind.SCANNER_LAYER, PageKind.GARBLED})
# With no page of running text, a cover's title is all the layer has: the
# pixels of these pages hold the rest.
_PICTURE_KINDS = frozenset({PageKind.BIG_IMAGE, PageKind.SPARSE})
# Pages between checks for a cancel, as a Docling batch is 8 pages.
CANCEL_EVERY = 8


@dataclass(frozen=True)
class OcrReading:
    """The layer with OCR's text on the pages it stands for, and why each page
    left for Docling went there."""

    layer: TextLayer
    docling: dict[int, str]
    read: int
    reader: str
    seconds: float
    # Kept from a run that gave the queue up to Docling's reading.
    resumed: bool = False


def ocr_reading(
    original: Path, layer: TextLayer, document: Document | None = None
) -> OcrReading | None:
    """None when there is nothing for OCR here, no OCR on this computer, or it
    failed: Docling then reads as before. Raises only JobCancelledError."""
    if not layer.pages:
        return None
    reader = page_reader()
    if reader is None:
        return None
    try:
        candidates = _candidates(original, layer)
        if not candidates:
            return None
        return _read(reader, original, layer, candidates, document)
    except JobCancelledError:
        raise
    except Exception:
        logger.warning(
            "%s could not read %s; Docling reads it",
            reader.name,
            original.name,
            exc_info=True,
        )
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


def _read(
    reader: PageReader,
    original: Path,
    layer: TextLayer,
    candidates: list[int],
    document: Document | None,
) -> OcrReading | None:
    started = time.perf_counter()
    kept = kept_reading(original, reader.name)
    if kept is not None:
        texts = {int(n): text for n, text in kept["texts"].items()}
        docling = {int(n): why for n, why in kept["docling"].items()}
    else:
        texts, docling, stood = _ocr(reader, original, layer, candidates, document)
        if not stood:
            # No page read as text: Docling reads the file whole, as before.
            return None
        if docling:
            keep_reading(original, reader.name, {"texts": texts, "docling": docling})
    pages: list[LayerPage] = list(layer.pages)
    for n, text in texts.items():
        pages[n - 1] = replace(pages[n - 1], text=text, refused_because=None)
    for n, page in enumerate(pages, start=1):
        if page.text is None and n not in docling:
            docling[n] = page.refused_because or f"page {n} is for Docling"
    return OcrReading(
        replace(layer, pages=tuple(pages)),
        docling,
        len(texts),
        reader.name,
        time.perf_counter() - started,
        resumed=kept is not None,
    )


def _ocr(
    reader: PageReader,
    original: Path,
    layer: TextLayer,
    candidates: list[int],
    document: Document | None,
) -> tuple[dict[int, str], dict[int, str], int]:
    """Each candidate page's text, why the others go to Docling, and how many read
    as text."""
    # The ingest job's own session; a reading outside one has nothing to check.
    session = object_session(document) if document is not None else None
    turn = reading_turn(session, document) if session and document else None
    texts: dict[int, str] = {}
    docling: dict[int, str] = {}
    stood = 0
    # Closed here, whatever stops the reading: its PDF closes under pdfium's lock,
    # which the garbage collector could otherwise take while this thread holds it.
    with closing(pdf_frames(original, candidates, reader.max_side)) as frames:
        for count, (frame, page) in enumerate(read_upright(reader, frames), start=1):
            if turn is not None and count % CANCEL_EVERY == 0:
                turn.check_cancelled()
            n, verdict = frame.number, page.verdict()
            if verdict not in KEPT:
                docling[n] = f"page {n} is {verdict}"
            elif verdict is PageVerdict.TEXT:
                texts[n] = page.text()
                stood += 1
            else:
                # Little or nothing read: a cover's own title, if it has one, wins.
                texts[n] = layer.pages[n - 1].text or page.text()
    return texts, docling, stood
