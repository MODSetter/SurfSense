"""A PDF with a few pages only Docling can read: Docling reads those pages, the
text layer the rest, and the text joins them in page order. A scan, a filled
form and a file pdfium cannot open are still read by Docling whole."""

import io
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import PRIORITY_IDLE
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests import pdf_samples
from tests.integration.worker.paged_docling_stand_in import PagedDocling
from worker.ingestion import run

pytestmark = pytest.mark.integration

REPORT = pdf_samples.prose(9, seed=7)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def upload(session: Session, pdf: bytes, name: str = "report.pdf") -> Document:
    """A pending PDF upload with its original on disk, as the upload route leaves it."""
    workspace = Workspace(name="Harbour")
    session.add(workspace)
    session.flush()
    source = Document(
        workspace_id=workspace.id, title=name, document_type=DocumentType.FILE
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(pdf)
    return source


def scans(pages: int) -> bytes:
    """Pages that are each one picture and no text, as a scanner writes them."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for n in range(pages):
        pixels = io.BytesIO()
        Image.new("RGB", (60, 85), (250, 250, 240 - n)).save(pixels, "PNG")
        drawing.drawImage(ImageReader(pixels), 0, 0, width=A4[0], height=A4[1])
        drawing.showPage()
    drawing.save()
    return out.getvalue()


def filled_form_with_a_scan() -> bytes:
    """A claim form typed into, two pages of notes, and a scanned receipt."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    drawing.drawString(72, 760, "Claimant name:")
    drawing.acroForm.textfield(
        name="claimant", value="Ingrid Solheim", x=250, y=755, width=230, height=20
    )
    drawing.showPage()
    for paragraphs in (REPORT[:3], REPORT[3:6]):
        text = drawing.beginText(72, 760)
        for paragraph in paragraphs:
            text.textLine(paragraph[:90])
        drawing.drawText(text)
        drawing.showPage()
    pixels = io.BytesIO()
    Image.new("RGB", (60, 85), "white").save(pixels, "PNG")
    drawing.drawImage(ImageReader(pixels), 0, 0, width=A4[0], height=A4[1])
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def folder_of(source: Document) -> Path:
    """The source's own folder, where its original and its figures live."""
    return get_storage_settings().document_dir(source.workspace_id, source.id)


def test_a_scanned_page_between_born_digital_ones_is_all_docling_reads(
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Its markdown takes the scanned page's place; the log says which pages."""
    pdf = pdf_samples.joined(
        pdf_samples.text_pages(REPORT[:3]),
        scans(1),
        pdf_samples.text_pages(REPORT[3:6]),
    )
    source = upload(session, pdf)
    caplog.set_level(logging.INFO, logger="worker.ingestion.pdf_reading.route")

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == [(2, 2)]
    assert source.content == "\n\n".join(
        [
            pdf_samples.set_text(REPORT[:3]),
            paged_docling.markdown(2, 2),
            pdf_samples.set_text(REPORT[3:6]),
        ]
    )
    assert "Docling reads page 2 of report.pdf: page 2 is ocr:no-text" in caplog.text


def test_a_turned_landscape_page_is_read_by_docling_alone(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """pdfium reads a turned page's lines last to first."""
    pdf = pdf_samples.turned(
        pdf_samples.text_pages(REPORT[:3], REPORT[3:6], REPORT[6:]), 1, 90
    )
    source = upload(session, pdf)

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [(2, 2)]
    assert source.content == "\n\n".join(
        [
            pdf_samples.set_text(REPORT[:3]),
            paged_docling.markdown(2, 2),
            pdf_samples.set_text(REPORT[6:]),
        ]
    )


def test_a_picture_on_a_turned_page_alone_queues_the_idle_pass(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Its images count, though its text is Docling's."""
    pdf = pdf_samples.turned(
        pdf_samples.joined(
            pdf_samples.text_pages(REPORT[:3]),
            pdf_samples.illustrated(REPORT[3:6]),
            pdf_samples.text_pages(REPORT[6:]),
        ),
        1,
        90,
    )
    source = upload(session, pdf)

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [(2, 2)]
    assert [(t.name, t.args, t.priority) for t in ingest_queue.pending()] == [
        ("extract_figures", (source.id,), PRIORITY_IDLE)
    ]


def test_runs_of_flagged_pages_are_each_read_in_one_go(
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A run of consecutive pages is one reading; the pages between stay text."""
    text = pdf_samples.text_pages(REPORT[:3])
    pdf = pdf_samples.joined(scans(1), text, text, scans(2), text, text, text)
    source = upload(session, pdf)
    caplog.set_level(logging.INFO, logger="worker.ingestion.pdf_reading.route")

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [(1, 1), (4, 5)]
    page = pdf_samples.set_text(REPORT[:3])
    assert source.content == "\n\n".join(
        [
            paged_docling.markdown(1, 1),
            page,
            page,
            paged_docling.markdown(4, 5),
            page,
            page,
            page,
        ]
    )
    assert "Docling reads pages 1, 4-5 of report.pdf: page 1 is ocr:no-text" in (
        caplog.text
    )


def test_a_spliced_pdf_keeps_no_figures_at_ingest_and_queues_the_idle_pass(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """As a text-read PDF: its figures come from the figures-only pass."""
    paged_docling.pictured = {1}
    source = upload(session, pdf_samples.cover_page("Education", REPORT[:4]))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == [(1, 1)]
    assert not (folder_of(source) / "figures" / "figures.json").exists()
    assert [(t.name, t.args, t.priority) for t in ingest_queue.pending()] == [
        ("extract_figures", (source.id,), PRIORITY_IDLE)
    ]


def test_a_mostly_scanned_pdf_is_read_by_docling_whole_with_its_figures(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Over half its pages flagged: a scan with a typed page, read as before."""
    paged_docling.pictured = {2}
    pdf = pdf_samples.joined(scans(2), pdf_samples.text_pages(REPORT[:3]))
    source = upload(session, pdf)

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [None]
    assert source.content == paged_docling.markdown(1, 3)
    assert (folder_of(source) / "figures" / "figures.json").is_file()


def test_a_filled_form_with_a_scanned_page_is_read_by_docling_whole(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Its answers live in its fields, which only Docling reads off the page."""
    source = upload(session, filled_form_with_a_scan())

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [None]


def test_flagged_pages_beside_covers_and_stamps_alone_go_to_docling_whole(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """With no page of running text, the content is in the pages' pixels."""
    sparse = pdf_samples.lines_page(["Appendix B"])
    source = upload(session, pdf_samples.joined(scans(1), sparse, sparse))

    run(source.id)

    session.expire_all()
    assert paged_docling.asked == [None]


def test_a_file_pdfium_cannot_open_is_given_to_docling_whole(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Docling says why it cannot read it, as before the text layer."""

    def damaged(_pages: object) -> None:
        raise ValueError("damaged")

    paged_docling.during = damaged
    source = upload(session, b"%PDF-1.7 not really")

    with pytest.raises(ValueError, match="damaged"):
        run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.FAILED
    assert paged_docling.asked == [None]
