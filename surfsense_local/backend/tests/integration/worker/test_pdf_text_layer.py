"""Ingest reads a born-digital PDF from its text layer, and its figures come later
from the figures-only pass; Docling reads every other PDF as before."""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures import FiguresPending, list_figures
from modules.documents.tasks import PRIORITY_ASKED, PRIORITY_IDLE
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests import pdf_samples
from tests.integration.worker.docling_stand_in import reading
from worker.ingestion import run
from worker.studio.office.document.figure_shelf import figures_of

pytestmark = pytest.mark.integration

REPORT = pdf_samples.prose(8, seed=4)
CAPTION = "Figure 1: Berth calls by quarter."


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def upload(session: Session, pdf: bytes) -> Document:
    """A pending PDF upload with its original on disk, as the upload route leaves it."""
    workspace = Workspace(name="Harbour")
    session.add(workspace)
    session.flush()
    source = Document(
        workspace_id=workspace.id, title="report.pdf", document_type=DocumentType.FILE
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    (folder / "report.pdf").write_bytes(pdf)
    return source


def figures_index_exists(source: Document) -> bool:
    """Whether ingest or the figures pass has kept the source's figures."""
    folder = get_storage_settings().document_dir(source.workspace_id, source.id)
    return (folder / "figures" / "figures.json").is_file()


def test_a_born_digital_pdf_is_ready_with_its_text_layer_as_content(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """The docling fixture fails the ingest if Docling is asked to read it."""
    pdf = pdf_samples.text_pages(REPORT[:4], REPORT[4:])
    source = upload(session, pdf)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert source.error_message is None
    assert source.content == pdf_samples.set_text(REPORT[:4], REPORT[4:])
    found = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Paragraph'")
    )
    assert found >= 1
    assert not figures_index_exists(source)


def test_with_the_switch_off_docling_reads_every_pdf(
    session: Session,
    stub_model: None,
    docling: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As before the text layer: Docling's reading, figures kept at ingest."""
    monkeypatch.setenv("SURFSENSE_LOCAL_PDF_TEXT_LAYER", "off")
    docling.append(reading())
    source = upload(session, pdf_samples.text_pages(REPORT))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert source.content == "Quarterly results."
    assert figures_index_exists(source)


def test_a_scan_is_read_by_docling_with_its_figures_kept_at_ingest(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Even with a scanner's OCR layer: Docling's own OCR is what reads it."""
    docling.append(reading({"caption": CAPTION, "page": 1, "box": (72, 500, 272, 650)}))
    source = upload(session, pdf_samples.scanned_page(REPORT[:4], ocr_layer=True))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert "Quarterly results." in (source.content or "")
    assert figures_index_exists(source)


def test_a_text_read_pdfs_figures_come_from_the_figures_pass_when_first_asked(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Until the pass has run, the agent hears its images are being extracted and
    Studio's shelf offers none; asking twice queues the pass once."""
    source = upload(session, pdf_samples.text_pages(REPORT))
    run(source.id)
    session.expire_all()
    content = source.content
    chunks = session.scalar(select(func.count()).select_from(Chunk))

    for _ in range(2):
        with pytest.raises(FiguresPending):
            list_figures(session, source.workspace_id, source.id)
    assert figures_of(session, source.workspace_id, [source.id]) == ()
    assert [task.args for task in ingest_queue.pending()] == [(source.id,)]

    docling.append(reading({"caption": CAPTION, "page": 1, "box": (72, 500, 272, 650)}))
    session.rollback()  # every transaction here takes the lock the pass's read needs
    ingest_queue.execute(ingest_queue.dequeue())

    listed = list_figures(session, source.workspace_id, source.id)
    assert [(figure.caption, figure.page) for figure in listed] == [(CAPTION, 1)]
    shelf = figures_of(session, source.workspace_id, [source.id])
    assert [figure.caption for figure in shelf] == [CAPTION]
    assert ingest_queue.pending_count() == 0
    session.expire_all()
    assert source.content == content
    assert session.scalar(select(func.count()).select_from(Chunk)) == chunks


def test_a_text_read_pdf_with_a_photo_has_its_figures_kept_once_the_queue_is_idle(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Ready at once; the figures pass waits below every ingest, and asking for
    the figures meanwhile queues a copy that waits only behind notes and uploads."""
    source = upload(session, pdf_samples.illustrated(REPORT[:4]))

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert [(t.args, t.priority) for t in ingest_queue.pending()] == [
        ((source.id,), PRIORITY_IDLE)
    ]

    with pytest.raises(FiguresPending):
        list_figures(session, source.workspace_id, source.id)
    assert [(t.args, t.priority or 0) for t in ingest_queue.pending()] == [
        ((source.id,), PRIORITY_ASKED),
        ((source.id,), PRIORITY_IDLE),
    ]

    docling.append(reading({"caption": CAPTION, "page": 1, "box": (72, 72, 372, 297)}))
    session.rollback()  # every transaction here takes the lock the pass's read needs
    while ingest_queue.pending_count():
        ingest_queue.execute(ingest_queue.dequeue())

    listed = list_figures(session, source.workspace_id, source.id)
    assert [(figure.caption, figure.page) for figure in listed] == [(CAPTION, 1)]
    assert docling == []  # the idle copy found them kept and read nothing
