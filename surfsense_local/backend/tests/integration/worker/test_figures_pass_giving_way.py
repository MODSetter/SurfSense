"""The figures-only pass gives the queue up to any source that waits, once it has
had some 20 s, keeping the runs it has read, and carries on at the priority it
was queued with; ingest queues it at idle for a PDF with drawn charts too."""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument, Size
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import PRIORITY_IDLE, extract_figures
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests import pdf_samples
from tests.integration.worker.docling_stand_in import provenance
from worker.ingestion import run
from worker.ingestion.figures import queue_turn
from worker.ingestion.figures.idle_pass import IDLE_PASS_PAGES
from worker.ingestion.figures.run_reading import LayoutReading

pytestmark = pytest.mark.integration

REPORT = pdf_samples.prose(6, seed=3)
# Born-digital, born-digital, a scan, born-digital: three runs.
RUNS = [("layout", (1, 2)), ("full", (3, 3)), ("layout", (4, 4))]


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the pass opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Docling's layout and full readings of a run: a captioned picture on each
    page. `asked` records each reading's kind and pages."""
    seen = SimpleNamespace(asked=[])

    def reading(kind: str, first: int, last: int) -> DoclingDocument:
        seen.asked.append((kind, (first, last)))
        document = DoclingDocument(name="report")
        for page in range(first, last + 1):
            document.add_page(page_no=page, size=Size(width=A4[0], height=A4[1]))
            caption = document.add_text(
                label=DocItemLabel.CAPTION,
                text=f"Figure {page}: berth calls, {kind} reading.",
                prov=provenance(page, (72, 280, 372, 295)),
            )
            document.add_picture(
                prov=provenance(page, (72, 300 + page, 372, 525)), caption=caption
            )
        return document

    monkeypatch.setattr(
        "worker.ingestion.figures.run_reading.read_in_full",
        lambda _pdf, first, last: reading("full", first, last),
    )
    monkeypatch.setattr(
        "worker.ingestion.figures.run_reading.read_by_layout",
        lambda _pdf, first, last: LayoutReading(
            reading("layout", first, last), frozenset()
        ),
    )
    return seen


@pytest.fixture
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 20 s the pass has before it gives way, cut for the test."""
    monkeypatch.setattr(queue_turn, "YIELD_AFTER_SECONDS", 0.0)


def report_with_a_scan() -> bytes:
    """Two pages of report, a scanned page bound in, and a last page of report."""
    text = pdf_samples.text_pages(REPORT[:3])
    return pdf_samples.joined(
        text, text, pdf_samples.scanned_page(REPORT[3:], ocr_layer=False), text
    )


def add_source(
    session: Session,
    pdf: bytes,
    name: str = "report.pdf",
    status: DocumentStatus = DocumentStatus.READY,
) -> Document:
    """A source with its original on disk."""
    workspace = session.query(Workspace).first()
    if workspace is None:
        workspace = Workspace(name="Harbour")
        session.add(workspace)
        session.flush()
    source = Document(
        workspace_id=workspace.id,
        title=name,
        document_type=DocumentType.FILE,
        status=status,
        content="The text ingest extracted.",
    )
    session.add(source)
    session.commit()
    folder = folder_of(source)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(pdf)
    return source


def add_waiting_note(session: Session) -> Document:
    """A note written while the pass runs, waiting for the queue."""
    note = Document(
        workspace_id=session.query(Workspace).first().id,
        title="Berth plan",
        document_type=DocumentType.NOTE,
        content="Berth four reopens on Monday.",
    )
    session.add(note)
    session.commit()
    return note


def folder_of(source: Document) -> Path:
    """The source's own folder, where its original and its figures live."""
    return get_storage_settings().document_dir(source.workspace_id, source.id)


def figures(source: Document) -> dict[str, bytes]:
    """Every file the pass kept for the source, by name."""
    kept = folder_of(source) / "figures"
    return {path.name: path.read_bytes() for path in sorted(kept.iterdir())}


def run_queued() -> None:
    """The ingest worker takes the next job."""
    ingest_queue.execute(ingest_queue.dequeue())


@pytest.mark.parametrize("priority", [PRIORITY_IDLE, 0], ids=["idle", "asked"])
def test_the_pass_gives_way_to_a_waiting_source_and_queues_again(
    session: Session,
    runs: SimpleNamespace,
    no_wait: None,
    priority: int,
) -> None:
    """At the priority it came with, its runs kept and figures.json not yet written."""
    source = add_source(session, report_with_a_scan())
    note = add_waiting_note(session)
    extract_figures(source.id, priority=priority)

    run_queued()

    assert runs.asked == RUNS[:1]
    assert not (folder_of(source) / "figures" / "figures.json").exists()
    kept = folder_of(source) / "figures" / "work"
    assert sorted(path.name for path in kept.glob("layout-*.json")) == [
        "layout-1-2.json"
    ]
    assert [(t.name, t.args, t.priority or 0) for t in ingest_queue.pending()] == [
        ("extract_figures", (source.id,), priority)
    ]

    session.delete(note)
    session.commit()
    run_queued()

    assert runs.asked == RUNS
    index = json.loads(figures(source)["figures.json"])
    assert [entry["page"] for entry in index["figures"]] == [1, 2, 3, 4]
    assert not (folder_of(source) / "figures" / "work").exists()
    assert ingest_queue.pending_count() == 0


def test_a_resumed_pass_keeps_the_very_figures_of_an_uninterrupted_one(
    session: Session, runs: SimpleNamespace, no_wait: None
) -> None:
    """figures.json and every PNG, byte for byte."""
    straight = add_source(session, report_with_a_scan(), name="straight.pdf")
    extract_figures.call_local(straight.id)
    resumed = add_source(session, report_with_a_scan(), name="resumed.pdf")
    note = add_waiting_note(session)
    for _turn in range(2):
        extract_figures(resumed.id, priority=PRIORITY_IDLE)
        run_queued()
        assert ingest_queue.pending_count() == 1  # it gave way again
        ingest_queue.flush()
    session.delete(note)
    session.commit()

    extract_figures(resumed.id, priority=PRIORITY_IDLE)
    run_queued()

    assert figures(resumed) == figures(straight)
    assert len(figures(straight)) == 5  # figures.json and four PNGs
    # Each run read once for each source.
    assert runs.asked == RUNS + RUNS


def test_the_pass_does_not_give_way_before_its_time(
    session: Session, runs: SimpleNamespace
) -> None:
    """The 20 s keeps a short file's pass whole."""
    source = add_source(session, report_with_a_scan())
    add_waiting_note(session)

    extract_figures.call_local(source.id)

    assert runs.asked == RUNS
    assert "figures.json" in figures(source)


def chart_page(bars: int) -> bytes:
    """A page of report and a bar chart drawn as filled rectangles, no image."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    text = drawing.beginText(72, 700)
    for paragraph in REPORT[:3]:
        text.textLine(paragraph[:90])
    drawing.drawText(text)
    drawing.line(72, 300, 500, 300)
    drawing.line(72, 300, 72, 600)
    for bar in range(bars):
        drawing.rect(90 + bar * 40, 300, 25, 40 + bar * 20, fill=1)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def test_ingest_queues_the_idle_pass_for_a_chart_drawn_as_paths(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """No image object, but enough drawing for a chart; the docling fixture fails
    the test if Docling is asked to read it."""
    source = add_source(session, chart_page(bars=8), status=DocumentStatus.PENDING)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert [(t.name, t.args, t.priority) for t in ingest_queue.pending()] == [
        ("extract_figures", (source.id,), PRIORITY_IDLE)
    ]


def test_ingest_leaves_a_long_pdf_to_be_asked(
    session: Session, stub_model: None, docling: list[Any]
) -> None:
    """Background CPU stays bounded; the first ask queues the pass."""
    photo = io.BytesIO()
    Image.new("RGB", (40, 30), "orange").save(photo, "PNG")
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for _page in range(IDLE_PASS_PAGES + 1):
        text = drawing.beginText(72, 600)
        for paragraph in REPORT[:3]:
            text.textLine(paragraph[:90])
        drawing.drawText(text)
        drawing.drawImage(ImageReader(photo), 72, 300, width=300, height=225)
        drawing.showPage()
    drawing.save()
    source = add_source(session, out.getvalue(), status=DocumentStatus.PENDING)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert ingest_queue.pending_count() == 0
