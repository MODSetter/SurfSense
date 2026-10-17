"""An uploaded image read by OCR alone, before Docling is asked.

All of it or none: Docling reads a multi-frame TIFF as one stream, so a frame
OCR's text cannot stand for sends the whole file to Docling, as before.
"""

import logging
import time
from contextlib import closing
from pathlib import Path

from worker.ingestion.pdf_text_layer.reading import PAGE_BREAK
from worker.ingestion.scan_ocr.frames import image_frames
from worker.ingestion.scan_ocr.page import KEPT, PageVerdict
from worker.ingestion.scan_ocr.reader import page_reader
from worker.ingestion.scan_ocr.upright import read_upright

logger = logging.getLogger(__name__)


def image_markdown(path: Path) -> str | None:
    """None when Docling should read it: no OCR here, a garbled frame, no frame
    that reads as text, or a failure. Never raises."""
    reader = page_reader()
    if reader is None:
        return None
    started = time.perf_counter()
    texts: list[str] = []
    stood = False
    try:
        with closing(image_frames(path, reader.max_side)) as frames:
            for frame, page in read_upright(reader, frames):
                verdict = page.verdict()
                if verdict not in KEPT:
                    logger.info(
                        "Docling reads %s: frame %d is %s",
                        path.name,
                        frame.number,
                        verdict,
                    )
                    return None
                if verdict is not PageVerdict.BLANK:
                    texts.append(page.text())
                stood = stood or verdict is PageVerdict.TEXT
    except Exception:
        logger.warning(
            "%s could not read %s; Docling reads it",
            reader.name,
            path.name,
            exc_info=True,
        )
        return None
    if not stood:
        # As for a PDF: with no frame of text, Docling reads it whole.
        return None
    logger.info(
        "%s reads %s in %.1f s", reader.name, path.name, time.perf_counter() - started
    )
    return PAGE_BREAK.join(texts)
