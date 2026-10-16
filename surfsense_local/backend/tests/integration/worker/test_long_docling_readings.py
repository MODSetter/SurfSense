"""A long Docling reading goes a batch of pages at a time: between batches it checks
for a cancel and, once it has had its minute, gives the queue up to an upload
queued at its priority or above, carrying on later from the batches it kept."""

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
from modules.documents.tasks import (
    PRIORITY_BULK,
    PRIORITY_INTERACTIVE,
    ingest_document,
)
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests import pdf_samples
from tests.integration.worker.paged_docling_stand_in import PagedDocling
from worker.ingestion import pipeline, run
from worker.ingestion.docling_batches import queue_turn
from worker.interrupted_documents import fail_interrupted_documents

pytestmark = pytest.mark.integration

BATCHES = [(1, 8), (9, 16), (17, 20)]
REPORT = pdf_samples.prose(3, seed=7)


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


def upload(
    session: Session,
    pdf: bytes,
    name: str = "scan.pdf",
    priority: int = PRIORITY_INTERACTIVE,
    metadata: dict[str, str] | None = None,
) -> Document:
    """A pending upload with its original on disk and its job queued, as the
    upload route leaves it; a bulk copy queues its files at bulk priority."""
    source = Document(
        workspace_id=workspace(session),
        title=name,
        document_type=DocumentType.FILE,
        document_metadata=metadata,
    )
    session.add(source)
    session.commit()
    folder = folder_of(source)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(pdf)
    ingest_document(source.id, priority=priority)
    return source


def write_note(session: Session, queued: bool = True) -> Document:
    """A note written mid-reading, its job queued as the notes route queues it;
    not `queued`, a row left pending with no job, as a lost one would be."""
    with create_session_factory(session.get_bind())() as api:
        note = Document(
            workspace_id=workspace(api),
            title="Berth plan",
            document_type=DocumentType.NOTE,
            content="Berth four reopens on Monday.",
        )
        api.add(note)
        api.commit()
        if queued:
            ingest_document(note.id)
        return note


def give_way_once(session: Session, source: Document) -> Document:
    """The reading's first run, a note written before it: it reads one batch and
    gives way. Only the note's job and its own are left queued."""
    ingest_queue.flush()
    note = write_note(session)
    run(source.id)
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
    """Pending, at the priority it came with, with the batch it read kept."""
    source = upload(session, scan(20))

    note = give_way_once(session, source)

    session.expire_all()
    assert source.status is DocumentStatus.PENDING
    assert [(t.args, t.priority) for t in ingest_queue.pending()] == [
        ((note.id,), PRIORITY_INTERACTIVE),
        ((source.id,), PRIORITY_INTERACTIVE),
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
    give_way_once(session, source)
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
    give_way_once(session, source)
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
    note = give_way_once(session, source)
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
    note = give_way_once(session, resumed)
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


@pytest.mark.parametrize("lost", [8, 9], ids=["last-of-a-batch", "first-of-a-batch"])
def test_a_page_docling_lost_leaves_every_later_figure_on_its_own_page(
    session: Session, stub_model: None, paged_docling: PagedDocling, lost: int
) -> None:
    """Joining numbers each batch's pages on from the last; the lost page is kept
    empty, as one conversion of the file lacks it."""
    paged_docling.pictured = {3, 12, 19}
    paged_docling.lost = {lost}
    source = upload(session, scan(20))

    drain(session)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert f"Docling read page {lost}." not in (source.content or "")
    index = json.loads(
        (folder_of(source) / "figures" / "figures.json").read_text("utf-8")
    )
    assert [figure["page"] for figure in index["figures"]] == [3, 12, 19]


def test_a_short_scan_is_one_conversion_as_before(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """Eight pages or fewer: nothing to give way between, nothing kept."""
    source = upload(session, scan(8))

    drain(session)

    assert paged_docling.asked == [None]
    assert not docling_dir(folder_of(source)).exists()


def test_a_reading_does_not_give_way_to_one_that_gave_way_itself(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """Two long scans: the first gives way to the second once, which then reads
    to the end; taking turns would leave both waiting until the last batch."""
    first = upload(session, scan(20), name="first.pdf")
    second = upload(session, scan(20), name="second.pdf")

    outcomes = drain(session)

    assert outcomes == [
        ("ingest_document", first.id, "pending"),
        ("ingest_document", second.id, "ready"),
        ("ingest_document", first.id, "ready"),
    ]
    assert paged_docling.asked == [(1, 8), *BATCHES, (9, 16), (17, 20)]


def test_batches_kept_for_other_bytes_are_read_again(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """A checkpoint names the original it read: one replaced meanwhile, even by a
    file of the same size, starts over."""
    source = upload(session, scan(20))
    note = give_way_once(session, source)
    assert kept_batches(source) == ["pages-1-8"]
    original = folder_of(source) / "scan.pdf"
    pdf = original.read_bytes()
    replaced = pdf.replace(b"Generated PDF document", b"Generated PDF Document", 1)
    assert replaced != pdf
    assert len(replaced) == len(pdf)
    original.write_bytes(replaced)
    session.commit()
    set_status(session, note, DocumentStatus.READY)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == [(1, 8), *BATCHES]


async def test_a_reading_the_app_quit_in_carries_on_when_retried(
    client: AsyncClient,
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
) -> None:
    """The worker stopped mid-batch: the sweep fails the row, and Retry reads only
    the batches not kept."""
    source = upload(session, scan(20))

    def quit_app(pages: tuple[int, int] | None) -> None:
        if pages == (9, 16):
            raise KeyboardInterrupt

    paged_docling.during = quit_app
    with pytest.raises(KeyboardInterrupt):
        run(source.id)
    assert kept_batches(source) == ["pages-1-8"]
    fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})
    paged_docling.during = None
    ingest_queue.flush()

    retried = await client.post(
        f"/workspaces/{source.workspace_id}/documents/{source.id}/retry"
    )

    assert retried.status_code == 200
    drain(session)
    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == [(1, 8), (9, 16), (9, 16), (17, 20)]
    assert source.content == paged_docling.markdown(1, 20)
    assert not docling_dir(folder_of(source)).exists()


def test_a_reading_does_not_give_way_before_its_minute(
    session: Session, stub_model: None, paged_docling: PagedDocling
) -> None:
    """A note waiting from the start waits for a reading that has not had it."""
    source = upload(session, scan(20))
    note = write_note(session)

    outcomes = drain(session)

    assert outcomes == [
        ("ingest_document", source.id, "ready"),
        ("ingest_document", note.id, "ready"),
    ]
    assert paged_docling.asked == BATCHES


def test_a_reading_does_not_give_way_to_a_recording(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """A recording gives way to it in turn, so the two would take turns until
    both ended together."""
    source = upload(session, scan(20))
    ingest_queue.flush()
    upload(session, b"RIFF", "harbour.wav", metadata={"mime_type": "audio/wav"})

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == BATCHES


def test_a_reading_does_not_give_way_to_a_bulk_copy_started_after_it(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """The scan someone uploaded is ready before the folder they copied next;
    queued again behind the copy, it would wait out all of it."""
    source = upload(session, scan(20))
    copied: list[Document] = []

    def copy_starts(pages: tuple[int, int] | None) -> None:
        if pages == (1, 8):
            copied.extend(
                upload(session, b"Berth four reopens.", f"berth-{n}.txt", PRIORITY_BULK)
                for n in range(3)
            )

    paged_docling.during = copy_starts

    outcomes = drain(session)

    assert outcomes == [
        ("ingest_document", source.id, "ready"),
        *(("ingest_document", file.id, "ready") for file in copied),
    ]
    assert paged_docling.asked == BATCHES


def test_a_bulk_reading_gives_way_to_a_note_and_queues_again_at_bulk(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """Behind the note, and behind the rest of its own copy, not ahead of it."""
    source = upload(session, scan(20), priority=PRIORITY_BULK)
    notes: list[Document] = []

    def note_once(pages: tuple[int, int] | None) -> None:
        if pages == (1, 8):
            notes.append(write_note(session))

    paged_docling.during = note_once

    ingest_queue.execute(ingest_queue.dequeue())

    (note,) = notes
    session.expire_all()
    assert source.status is DocumentStatus.PENDING
    assert [(t.args, t.priority) for t in ingest_queue.pending()] == [
        ((note.id,), PRIORITY_INTERACTIVE),
        ((source.id,), PRIORITY_BULK),
    ]


def test_a_pending_row_with_no_job_queued_is_not_given_way_to(
    session: Session, stub_model: None, paged_docling: PagedDocling, no_minute: None
) -> None:
    """Nobody waits on it: giving way would cost the reading a turn for nothing.
    A job is queued, the reading's own copy, but not for that row."""
    source = upload(session, scan(20))
    write_note(session, queued=False)

    run(source.id)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert paged_docling.asked == BATCHES


def test_a_cancel_as_a_reading_gives_way_drops_its_batches(
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    no_minute: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It lands after the reading's last check: the job cannot queue again, and
    no run is left to clear them."""
    source = upload(session, scan(20))
    pause = pipeline.pause_job

    def cancelled_first(job: Session, document: Document) -> bool:
        set_status(session, source, DocumentStatus.CANCELLED)
        return pause(job, document)

    monkeypatch.setattr(pipeline, "pause_job", cancelled_first)

    note = give_way_once(session, source)

    session.expire_all()
    assert source.status is DocumentStatus.CANCELLED
    assert [t.args for t in ingest_queue.pending()] == [(note.id,)]
    assert not docling_dir(folder_of(source)).exists()


async def test_cancelling_the_folder_of_a_reading_that_gave_way_drops_its_batches(
    client: AsyncClient,
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    no_minute: None,
) -> None:
    """As cancelling the reading alone does."""
    created = await client.post("/workspaces", json={"name": "Harbour"})
    workspace_id = created.json()["id"]
    made = await client.post(
        f"/workspaces/{workspace_id}/folders", json={"parent_id": None, "name": "Scans"}
    )
    source = upload(session, scan(20))
    source.folder_id = made.json()["id"]
    session.commit()
    give_way_once(session, source)
    assert kept_batches(source) == ["pages-1-8"]
    session.commit()

    cancelled = await client.post(
        f"/workspaces/{workspace_id}/folders/{made.json()['id']}/cancel"
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] == [source.id]
    assert not docling_dir(folder_of(source)).exists()


def mixed_report() -> bytes:
    """Page 1 text, 2-11 scanned, 12-19 text, 20 scanned and 21-25 text: a run
    longer than a batch beside a run of one page."""
    text = pdf_samples.text_pages(REPORT)
    return pdf_samples.joined(text, scan(10), *([text] * 8), scan(1), *([text] * 5))


@pytest.mark.parametrize("gives_way", [False, True], ids=["straight", "resumed"])
def test_a_long_flagged_run_and_a_short_one_each_take_their_pages_place(
    session: Session,
    stub_model: None,
    paged_docling: PagedDocling,
    no_minute: None,
    gives_way: bool,
) -> None:
    """The long run's batches join into its pages' place, the short run takes its
    own, read straight through or resumed after giving way."""
    source = upload(session, mixed_report())

    def note_once(pages: tuple[int, int] | None) -> None:
        if gives_way and pages == (2, 9):
            write_note(session)

    paged_docling.during = note_once

    outcomes = drain(session)

    session.expire_all()
    assert source.status is DocumentStatus.READY
    assert (outcomes[0][2] == "pending") is gives_way
    # Then the idle figures pass, which this stand-in reads whole.
    assert paged_docling.asked[:3] == [(2, 9), (10, 11), (20, 20)]
    assert outcomes[-1][0] == "extract_figures"
    page = pdf_samples.set_text(REPORT)
    assert source.content == "\n\n".join(
        [
            page,
            paged_docling.markdown(2, 11),
            *([page] * 8),
            paged_docling.markdown(20, 20),
            *([page] * 5),
        ]
    )
