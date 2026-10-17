"""A scan or a photo read by OCR before Docling: the source is ready with OCR's
text, Docling reads only the pages OCR could not read, and with no OCR here Docling
reads as before. The OCR is a stand-in that returns pages of boxes."""

import io
from collections.abc import Iterable, Iterator

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from modules.documents.models import DocumentStatus
from modules.documents.tasks import PRIORITY_IDLE
from shared.queue import ingest_queue
from tests import pdf_samples
from tests.integration.worker.docling_stand_in import reading
from tests.integration.worker.paged_docling_stand_in import PagedDocling
from tests.integration.worker.test_mixed_pdfs import (
    REPORT,
    folder_of,
    scans,
    session,
    upload,
)
from worker.ingestion import run
from worker.ingestion.pdf_reading import ocr_first
from worker.ingestion.scan_ocr import images
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import Line, OcrPage, Word

pytestmark = pytest.mark.integration

__all__ = ["session"]


def prose(page: int) -> OcrPage:
    lines = tuple(
        Line(
            f"Scanned page {page} line {n} says the harbour board met.",
            tuple(
                Word(word, 100 + 120 * i, 200 + 45 * n, 100, 30)
                for i, word in enumerate(
                    f"Scanned page {page} line {n} says the harbour board met.".split()
                )
            ),
        )
        for n in range(8)
    )
    return OcrPage(1786, 2526, lines, 0.08, "en-US")


def garbled(page: int) -> OcrPage:
    """A page the engine was unsure of: it goes to Docling."""
    return OcrPage(1786, 2526, prose(page).lines, 0.08, "en-US", confidence=0.5)


class StandInOcr:
    name = "Stand-in OCR"
    language = "en-US"
    max_side = 2000

    def __init__(self) -> None:
        self.garbled: set[int] = set()
        self.read_pages: list[int] = []

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        for frame in frames:
            self.read_pages.append(frame.number)
            n = frame.number
            yield frame, garbled(n) if n in self.garbled else prose(n)


@pytest.fixture
def ocr(monkeypatch: pytest.MonkeyPatch) -> StandInOcr:
    reader = StandInOcr()
    monkeypatch.setattr(ocr_first, "page_reader", lambda: reader)
    monkeypatch.setattr(images, "page_reader", lambda: reader)
    return reader


def test_a_scan_is_ready_with_ocrs_text_and_docling_is_never_asked(
    session: Session, stub_model: None, paged_docling: PagedDocling, ocr: StandInOcr
) -> None:
    source = upload(session, scans(3))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == []
    assert ocr.read_pages == [1, 2, 3]
    assert "Scanned page 2 line 0 says the harbour board met." in (source.content or "")


def test_a_garbled_page_of_a_scan_is_read_by_docling_in_its_place(
    session: Session, stub_model: None, paged_docling: PagedDocling, ocr: StandInOcr
) -> None:
    ocr.garbled = {2}
    source = upload(session, scans(3))

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [(2, 2)]
    parts = (source.content or "").split("\n\n")
    assert paged_docling.markdown(2, 2) in source.content
    assert parts.index(paged_docling.markdown(2, 2)) > 0
    assert "Scanned page 3 line 7" in parts[-1]


def test_a_scans_figures_wait_to_be_asked_for(
    session: Session, stub_model: None, paged_docling: PagedDocling, ocr: StandInOcr
) -> None:
    """The pass would read every scanned page with Docling in full."""
    source = upload(session, scans(2))

    run(source.id)

    assert ingest_queue.pending() == []
    assert not (folder_of(source) / "figures" / "figures.json").exists()


def test_a_mixed_pdf_read_with_ocr_still_gets_its_idle_figures_pass(
    session: Session, stub_model: None, paged_docling: PagedDocling, ocr: StandInOcr
) -> None:
    """Its born-digital pages are read by layout alone, as before."""
    pdf = pdf_samples.joined(
        pdf_samples.text_pages(REPORT[:3]),
        scans(1),
        pdf_samples.text_pages(REPORT[3:6]),
    )
    source = upload(session, pdf)

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == []
    assert "Scanned page 2 line 0" in (source.content or "")
    assert [(t.name, t.args, t.priority) for t in ingest_queue.pending()] == [
        ("extract_figures", (source.id,), PRIORITY_IDLE)
    ]


def test_with_no_ocr_here_docling_reads_the_scan_whole(
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ocr_first, "page_reader", lambda: None)
    source = upload(session, scans(3))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == [None]


def photo() -> bytes:
    pixels = io.BytesIO()
    Image.new("RGB", (900, 1200), "white").save(pixels, "JPEG")
    return pixels.getvalue()


def test_a_photo_is_read_by_ocr_and_is_its_own_figure(
    session: Session, stub_model: None, paged_docling: PagedDocling, ocr: StandInOcr
) -> None:
    source = upload(session, photo(), name="receipt.jpg")

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == []
    assert "Scanned page 1 line 0" in (source.content or "")
    assert (folder_of(source) / "figures" / "figures.json").is_file()


def test_a_photo_ocr_cannot_read_is_read_by_docling_whole(
    session: Session, stub_model: None, docling: list, ocr: StandInOcr
) -> None:
    """A garbled frame: Docling reads the image, as before."""
    ocr.garbled = {1}
    docling.append(reading())
    source = upload(session, photo(), name="receipt.jpg")

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert source.content == "Quarterly results."
    assert docling == []
