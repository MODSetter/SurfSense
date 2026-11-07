"""Apple's Vision, on a Mac only: it reads a rendered page through PyObjC, and is
the reader a Mac picks first."""

import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from tests.integration.worker.test_rapidocr_engine import a_page
from worker.ingestion.scan_ocr import reader
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.images import image_markdown
from worker.ingestion.scan_ocr.page import PageVerdict
from worker.ingestion.scan_ocr.vision import _recognise

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


def test_the_options_survive_what_macos_27_does_to_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vision copies them and removes a key that is not there, which a Python dict's
    proxy refuses. Older macOS never does, so this repeats that step on any of them."""
    passed = []

    class Handler:
        @staticmethod
        def alloc() -> "Handler":
            return Handler()

        def initWithCGImage_options_(self, _image: object, options: object) -> None:  # noqa: N802
            passed.append(options)
            raise RuntimeError("seen")

    monkeypatch.setitem(
        sys.modules, "Vision", SimpleNamespace(VNImageRequestHandler=Handler)
    )

    with pytest.raises(RuntimeError, match="seen"):
        _recognise(Frame(1, Image.new("L", (8, 8), 255), 0.0))

    (options,) = passed
    options.mutableCopy().removeObjectForKey_("VNImageOptionProperties")


def test_a_vision_that_cannot_read_is_never_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting proves nothing: macOS 27 refused every page of a Vision that started."""

    def refuses(_frame: Frame) -> None:
        raise ValueError("NSInvalidArgumentException - key does not exist")

    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "auto")
    monkeypatch.setattr("worker.ingestion.scan_ocr.vision._recognise", refuses)
    reader.vision_reader.cache_clear()
    try:
        chosen = reader.page_reader()
    finally:
        reader.vision_reader.cache_clear()

    assert chosen is not None and chosen.name == "RapidOCR"


def test_an_uploaded_scan_is_read_by_vision_without_docling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path a Mac user's photo takes: None here would send it to Docling."""
    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "auto")
    reader.vision_reader.cache_clear()
    scan = tmp_path / "scan.png"
    a_page().save(scan)

    markdown = image_markdown(scan)

    assert markdown is not None
    assert "harbour board met on Tuesday" in markdown


@pytest.fixture
def vision_hangs(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every Vision read from here on sticks inside Apple's call, as one did on macOS 27."""
    released = threading.Event()

    def stuck(_frame: Frame) -> None:
        released.wait()

    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "auto")
    monkeypatch.setattr("worker.ingestion.scan_ocr.vision.READ_SECONDS", 0.2)
    reader.vision_reader.cache_clear()
    assert reader.vision_reader() is not None
    monkeypatch.setattr("worker.ingestion.scan_ocr.vision._recognise", stuck)
    yield
    released.set()
    reader.vision_reader.cache_clear()


@pytest.mark.usefixtures("vision_hangs")
def test_a_stuck_read_sends_that_scan_to_docling_and_later_ones_to_rapidocr(
    tmp_path: Path,
) -> None:
    """A native call cannot be killed: the document must not wait on it, and the
    next must not spend the limit finding the same thing out."""
    scan = tmp_path / "scan.png"
    a_page().save(scan)

    assert image_markdown(scan) is None

    chosen = reader.page_reader()
    assert chosen is not None and chosen.name == "RapidOCR"


def test_a_vision_that_sticks_on_its_first_read_is_never_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check at start is a read like any other, and needs the same limit."""
    released = threading.Event()

    def stuck(_frame: Frame) -> None:
        released.wait()

    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "auto")
    monkeypatch.setattr("worker.ingestion.scan_ocr.vision.READ_SECONDS", 0.2)
    monkeypatch.setattr("worker.ingestion.scan_ocr.vision._recognise", stuck)
    reader.vision_reader.cache_clear()
    try:
        chosen = reader.page_reader()
    finally:
        released.set()
        reader.vision_reader.cache_clear()

    assert chosen is not None and chosen.name == "RapidOCR"
