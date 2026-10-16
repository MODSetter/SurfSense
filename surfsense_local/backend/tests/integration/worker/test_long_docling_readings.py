"""A long Docling reading goes a batch of pages at a time: between batches it checks
for a cancel and, once it has had its minute, gives the queue up to an upload,
carrying on later from the batches it kept."""

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.docling_batches.layout import batches_dir, docling_dir
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import PRIORITY_BULK, ingest_document
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests.integration.worker.paged_docling_stand_in import PagedDocling
from worker.ingestion import run
from worker.ingestion.audio import queue_turn
from worker.interrupted_documents import fail_interrupted_documents

pytestmark = pytest.mark.integration

BATCHES = [(1, 8), (9, 16), (17, 20)]


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def no_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    """The minute a reading has before it gives way, cut for the test."""
    monkeypatch.setattr(queue_turn, "YIELD_AFTER_SECONDS", 0.0)


def scan(pages: int) -> bytes:
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


def workspace(session: Session) -> int:
    """The one workspace of the test."""
    found = session.query(Workspace).first()
    if found is None:
        found = Workspace(name="Harbour")
        session.add(found)
        session.commit()
    return found.id


def upload(session: Session, pdf: bytes, name: str = "scan.pdf") -> Document:
    """A pending PDF upload with its original on disk and its job queued, as the
    upload route leaves it."""
    source = Document(
        workspace_id=workspace(session), title=name, document_type=DocumentType.FILE
    )
    session.add(source)
    session.commit()
    folder = folder_of(source)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(pdf)
    ingest_document(source.id)
    return source


def write_note(session: Session) -> Document:
    """A note written mid-reading, its job queued as the notes route queues it."""
    with create_session_factory(session.get_bind())() as api:
        note = Document(
            workspace_id=workspace(api),
            title="Berth plan",
            document_type=DocumentType.NOTE,
            content="Berth four reopens on Monday.",
        )
        api.add(note)
        api.commit()
        ingest_document(note.id)
        return note


def set_status(session: Session, document: Document, status: DocumentStatus) -> None:
    """As another connection, the API's, writes it."""
    with create_session_factory(session.get_bind())() as api:
        api.get(Document, document.id).status = status
        api.commit()


def folder_of(source: Document) -> Path:
    """The source's own folder, where its original and its work live."""
    return get_storage_settings().document_dir(source.workspace_id, source.id)


def kept_batches(source: Document) -> list[str]:
    """The batches the reading kept for its next run."""
    folder = batches_dir(folder_of(source))
    return sorted(path.stem for path in folder.glob("pages-*.json"))


def drain(session: Session) -> list[tuple[str, int, str]]:
    """Run the queue as the ingest worker does, noting each job's outcome."""
    outcomes = []
    while ingest_queue.pending_count():
        task = ingest_queue.dequeue()
        ingest_queue.execute(task)
        document_id = task.args[0]
        session.expire_all()
        outcomes.append(
            (task.name, document_id, session.get(Document, document_id).status.value)
        )
        session.commit()
    return outcomes


def test_a_long_scan_is_read_in_batches_and_kept_whole(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Its text and figures are those of one reading; the batches go once read."""
    paged_docling.pictured = {3, 12, 19}
    source = upload(session, scan(20))

    drain(session)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == BATCHES
    assert source.content == paged_docling.markdown(1, 20)
    index = json.loads(
        (folder_of(source) / "figures" / "figures.json").read_text("utf-8")
    )
    assert [figure["page"] for figure in index["figures"]] == [3, 12, 19]
    assert not docling_dir(folder_of(source)).exists()


def test_a_note_written_during_a_long_reading_is_ready_before_it(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """The reading gives the queue up after its batch, and carries on after the note."""
    source = upload(session, scan(20))
    notes: list[Document] = []

    def note_once(pages: tuple[int, int] | None) -> None:
        if pages == (1, 8):
            notes.append(write_note(session))

    paged_docling.during = note_once

    outcomes = drain(session)

    (note,) = notes
    assert outcomes == [
        ("ingest_document", source.id, "pending"),
        ("ingest_document", note.id, "ready"),
        ("ingest_document", source.id, "ready"),
    ]
    assert paged_docling.asked == BATCHES
    session.expire_all()
    assert source.content == paged_docling.markdown(1, 20)


def test_a_reading_that_gave_way_is_queued_again_behind_the_upload(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """Pending, at bulk priority, with the batch it read kept."""
    source = upload(session, scan(20))
    note = write_note(session)
    ingest_queue.flush()

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.PENDING
    assert [(t.args, t.priority) for t in ingest_queue.pending()] == [
        ((source.id,), PRIORITY_BULK)
    ]
    assert kept_batches(source) == ["pages-1-8"]
    assert paged_docling.asked == [(1, 8)]
    session.commit()  # the reads above hold the write lock
    set_status(session, note, DocumentStatus.READY)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == BATCHES
    assert source.content == paged_docling.markdown(1, 20)
    assert not docling_dir(folder_of(source)).exists()


def test_a_cancel_mid_reading_stops_it_after_the_batch(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """The batch in flight finishes; no other is read, and the batches go."""
    source = upload(session, scan(20))

    def cancel(pages: tuple[int, int] | None) -> None:
        if pages == (9, 16):
            set_status(session, source, DocumentStatus.CANCELLED)

    paged_docling.during = cancel

    drain(session)

    session.expire_all()
    assert source.status is DocumentStatus.CANCELLED
    assert paged_docling.asked == [(1, 8), (9, 16)]
    assert not docling_dir(folder_of(source)).exists()


async def test_a_reading_deleted_while_it_gave_way_is_gone_with_its_batches(
    client: AsyncClient,
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    no_minute: None,
) -> None:
    """Delete takes a pending source; its queued job then finds nothing to read."""
    source = upload(session, scan(20))
    write_note(session)
    ingest_queue.flush()
    run(source.id)
    session.expire_all()
    assert source.status is DocumentStatus.PENDING
    session.commit()

    deleted = await client.delete(
        f"/workspaces/{source.workspace_id}/documents/{source.id}"
    )

    assert deleted.status_code == 204
    assert not folder_of(source).exists()
    run(source.id)
    assert paged_docling.asked == [(1, 8)]


async def test_cancelling_a_reading_that_gave_way_drops_its_batches(
    client: AsyncClient,
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    no_minute: None,
) -> None:
    """No run of its job is left to clear them."""
    source = upload(session, scan(20))
    write_note(session)
    ingest_queue.flush()
    run(source.id)
    assert kept_batches(source) == ["pages-1-8"]
    session.commit()

    cancelled = await client.post(
        f"/workspaces/{source.workspace_id}/documents/{source.id}/cancel"
    )

    assert cancelled.status_code == 200
    assert not docling_dir(folder_of(source)).exists()


def test_a_reading_that_gave_way_survives_a_restart_and_carries_on(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """The startup sweep fails only processing rows; a pending one keeps its batches."""
    source = upload(session, scan(20))
    note = write_note(session)
    ingest_queue.flush()
    run(source.id)
    set_status(session, note, DocumentStatus.READY)

    fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})

    session.expire_all()
    assert source.status is DocumentStatus.PENDING
    assert kept_batches(source) == ["pages-1-8"]
    session.commit()
    run(source.id)
    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == BATCHES
    assert source.content == paged_docling.markdown(1, 20)


def test_a_resumed_reading_equals_one_read_in_a_single_run(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """Text and figures alike, though its first batch came back from disk."""
    paged_docling.pictured = {2, 10, 18}
    straight = upload(session, scan(20), name="straight.pdf")
    run(straight.id)
    resumed = upload(session, scan(20), name="resumed.pdf")
    note = write_note(session)
    ingest_queue.flush()
    run(resumed.id)
    set_status(session, note, DocumentStatus.READY)
    session.commit()

    run(resumed.id)

    session.expire_all()
    assert (straight.status, resumed.status) == (DocumentStatus.READY,) * 2
    assert resumed.content == straight.content
    for kept in ("figures.json", "1.png", "2.png", "3.png"):
        assert (folder_of(resumed) / "figures" / kept).read_bytes() == (
            folder_of(straight) / "figures" / kept
        ).read_bytes()


def test_a_batch_that_lost_a_page_leaves_the_figures_to_the_figures_pass(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Joining would move every later picture onto the page before its own."""
    paged_docling.pictured = {12}
    paged_docling.lost = {8}
    source = upload(session, scan(20))

    drain(session)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert "Docling read page 12." in (source.content or "")
    assert not (folder_of(source) / "figures" / "figures.json").exists()


def test_a_short_scan_is_one_conversion_as_before(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Eight pages or fewer: nothing to give way between, nothing kept."""
    source = upload(session, scan(8))

    drain(session)

    assert paged_docling.asked == [None]
    assert not docling_dir(folder_of(source)).exists()
