"""The OCR that reads scans and photos before Docling, or None: then Docling reads
as before."""

import logging
import sys
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Protocol

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.switch import ScanOcr, scan_ocr_choice

log = logging.getLogger(__name__)


class PageReader(Protocol):
    name: str
    language: str | None
    # The longest side a frame may have.
    max_side: int

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]: ...


def page_reader() -> PageReader | None:
    """None when switched off, or when nothing here can read a page."""
    choice = scan_ocr_choice()
    if choice is ScanOcr.OFF:
        return None
    if choice is ScanOcr.AUTO and sys.platform == "darwin":
        return vision_reader() or rapid_reader()
    return rapid_reader()


@lru_cache(maxsize=1)
def rapid_reader() -> PageReader | None:
    """Once per process, so a missing model says so only the first time."""
    from worker.ingestion.scan_ocr.rapid import RapidOcr

    return _announced(RapidOcr.create(), RapidOcr.name)


@lru_cache(maxsize=1)
def vision_reader() -> PageReader | None:
    """Apple's Vision: on the corpus's real pages as good as RapidOCR but on
    forms, and the only reader of camera photos taken at an angle."""
    from worker.ingestion.scan_ocr.vision import VisionOcr

    return _announced(VisionOcr.create(), VisionOcr.name)


def _announced(reader: PageReader | None, name: str) -> PageReader | None:
    if reader is None:
        log.info("%s cannot read scans here", name)
    else:
        log.info("scans and photos are read by %s first", name)
    return reader
