"""Apple's Vision, on a Mac only: it reads a rendered page through PyObjC, and is
the reader a Mac picks first."""

import sys

import pytest

from tests.integration.worker.test_rapidocr_engine import a_page
from worker.ingestion.scan_ocr import reader
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import PageVerdict

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "darwin", reason="Vision is macOS's"),
]


def test_vision_reads_a_page_and_keeps_a_rows_cells_together() -> None:
    """Its line boxes go through the same reading order as RapidOCR's."""
    from worker.ingestion.scan_ocr.vision import VisionOcr

    vision = VisionOcr.create()
    assert vision is not None

    [(_, page)] = list(vision.read([Frame(1, a_page(), 0.05)]))
    text = page.text()

    assert page.verdict() is PageVerdict.TEXT
    assert "harbour board met on Tuesday" in text
    assert any("Wages" in line and "8,400" in line for line in text.splitlines())


def test_a_mac_reads_scans_with_vision_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """auto picks Vision on a Mac; rapidocr still picks RapidOCR."""
    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "auto")
    chosen = reader.page_reader()
    assert chosen is not None and chosen.name == "Vision"

    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "rapidocr")
    chosen = reader.page_reader()
    assert chosen is not None and chosen.name == "RapidOCR"
