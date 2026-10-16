"""Uploading a file: what lands in the row, on disk, and in the queue."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, text

from modules.documents import storage
from modules.documents.recordings.layout import work_files
from modules.documents.recordings.progress_file import (
    TranscriptionProgress,
    write_progress,
)
from modules.documents.tasks import PRIORITY_INTERACTIVE
from shared.config import get_storage_settings
from shared.queue import ingest_queue

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every document route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


def stored_files(data_dir: Path) -> list[Path]:
    """Everything under the data tree, so a stray temp file shows up too."""
    root = data_dir / "data"
    return sorted(path for path in root.rglob("*") if path.is_file())


async def test_an_upload_is_pending_on_disk_and_queued(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """The three things upload owes: a row to poll, the bytes, and a job."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7 fake", "application/pdf")},
    )

    assert response.status_code == 201
    created = response.json()["created"]
    assert [document["status"] for document in created] == ["pending"]
    assert created[0]["title"] == "report.pdf"

    stored = stored_files(data_dir)
    assert [path.name for path in stored] == ["report.pdf"]
    assert stored[0].read_bytes() == b"%PDF-1.7 fake"

    assert [(job.name, job.args) for job in ingest_queue.pending()] == [
        ("ingest_document", (created[0]["id"],))
    ]


async def test_the_same_bytes_are_not_ingested_twice(
    client: AsyncClient, workspace_id: int
) -> None:
    """Embedding a document twice doubles the work and splits its citations."""
    first = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-identical", "application/pdf")},
    )
    second = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("renamed.pdf", b"%PDF-identical", "application/pdf")},
    )

    assert second.status_code == 201
    assert second.json()["created"] == []
    original = first.json()["created"][0]
    assert second.json()["duplicates"] == [
        {
            "filename": "renamed.pdf",
            "document_id": original["id"],
            "folder_id": original["folder_id"],
        }
    ]


async def test_a_different_file_of_the_same_name_is_kept(
    client: AsyncClient, workspace_id: int
) -> None:
    """Dedup is on content, not filename: two different report.pdf files both land."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-january", "application/pdf")},
    )
    second = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-february", "application/pdf")},
    )

    assert len(second.json()["created"]) == 1
    assert second.json()["duplicates"] == []


async def test_the_same_file_is_kept_per_workspace(client: AsyncClient) -> None:
    """Workspaces are separate corpora; one is not allowed to shadow another."""
    first = await client.post("/workspaces", json={"name": "First"})
    second = await client.post("/workspaces", json={"name": "Second"})

    for workspace in (first, second):
        response = await client.post(
            f"/workspaces/{workspace.json()['id']}/documents/upload",
            files={"files": ("report.pdf", b"%PDF-shared", "application/pdf")},
        )

        assert len(response.json()["created"]) == 1


async def test_a_batch_is_split_rather_than_rejected(
    client: AsyncClient, workspace_id: int
) -> None:
    """A dropped folder holding one known file must not lose the other three."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("old.pdf", b"%PDF-seen before", "application/pdf")},
    )

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("old.pdf", b"%PDF-seen before", "application/pdf")),
            ("files", ("new.pdf", b"%PDF-never seen", "application/pdf")),
        ],
    )

    assert [document["title"] for document in response.json()["created"]] == ["new.pdf"]
    assert [entry["filename"] for entry in response.json()["duplicates"]] == ["old.pdf"]


async def test_unsupported_and_mismatched_files_are_rejected_per_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """Only verified formats reach storage and the ingestion queue."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("notes.txt", b"research notes", "application/octet-stream")),
            ("files", ("malware.exe", b"MZ", "application/pdf")),
            ("files", ("fake.pdf", b"MZ", "application/pdf")),
        ],
    )

    assert response.status_code == 201
    assert [entry["title"] for entry in response.json()["created"]] == ["notes.txt"]
    assert response.json()["rejected"] == [
        {"filename": "malware.exe", "reason": ".exe are not supported"},
        {
            "filename": "fake.pdf",
            "reason": "file contents do not match .pdf",
        },
    ]
    assert [path.name for path in stored_files(data_dir)] == ["notes.txt"]
    assert len(ingest_queue.pending()) == 1


async def test_a_recording_is_queued_and_an_opus_voice_note_is_turned_away(
    client: AsyncClient, workspace_id: int
) -> None:
    """MP3, FLAC and Ogg Vorbis are transcribed; Opus waits for its decoder,
    and the person reads why beside that one file."""
    tones = Path(__file__).resolve().parents[2] / "fixtures" / "audio"
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("standup.mp3", (tones / "tone.mp3").read_bytes(), "audio/x")),
            ("files", ("voice.ogg", (tones / "tone-opus.ogg").read_bytes(), "")),
            ("files", ("notes.txt", b"research notes", "text/plain")),
        ],
    )

    assert response.status_code == 201
    recording, notes = response.json()["created"]
    assert (recording["mime_type"], recording["transcription"]) == (
        "audio/mpeg",
        {"language": None, "progress": None, "awaiting": False},
    )
    assert notes["transcription"] is None
    assert response.json()["rejected"] == [
        {"filename": "voice.ogg", "reason": "Opus support comes in a later update"}
    ]
    assert len(ingest_queue.pending()) == 2


async def test_a_batch_is_queued_cheapest_first(
    client: AsyncClient, workspace_id: int
) -> None:
    """Huey runs equal priorities in the order queued, so a dropped batch
    becomes usable text first, then smallest first, recordings last."""
    tone = Path(__file__).resolve().parents[2] / "fixtures" / "audio" / "tone.mp3"
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("standup.mp3", tone.read_bytes(), "audio/mpeg")),
            ("files", ("big.pdf", b"%PDF-" + b"x" * 20_000, "application/pdf")),
            ("files", ("notes.md", b"# notes\n" + b"y" * 50_000, "text/markdown")),
            ("files", ("small.pdf", b"%PDF-1.7 small", "application/pdf")),
            ("files", ("todo.txt", b"call Ann", "text/plain")),
        ],
    )

    created = response.json()["created"]
    assert [document["title"] for document in created] == [
        "standup.mp3",
        "big.pdf",
        "notes.md",
        "small.pdf",
        "todo.txt",
    ]
    title_of = {document["id"]: document["title"] for document in created}
    queued = ingest_queue.pending()
    assert [title_of[job.args[0]] for job in queued] == [
        "todo.txt",
        "notes.md",
        "small.pdf",
        "big.pdf",
        "standup.mp3",
    ]
    assert {job.priority for job in queued} == {PRIORITY_INTERACTIVE}


async def test_a_queued_recording_reports_how_far_its_transcription_came(
    client: AsyncClient, workspace_id: int
) -> None:
    """Read from the job's progress file, so a reload sees what the events said."""
    tones = Path(__file__).resolve().parents[2] / "fixtures" / "audio"
    uploaded = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("lecture.flac", (tones / "tone.flac").read_bytes(), "")},
    )
    recording = uploaded.json()["created"][0]["id"]
    folder = get_storage_settings().document_dir(workspace_id, recording)
    progress = work_files(folder).progress
    progress.parent.mkdir(parents=True)
    write_progress(progress, TranscriptionProgress(done_s=1392.5, total_s=3480.0))

    listed = await client.get(f"/workspaces/{workspace_id}/documents")
    read = await client.get(f"/workspaces/{workspace_id}/documents/{recording}")

    expected = {
        "language": None,
        "progress": {"done_s": 1392.5, "total_s": 3480.0},
        "awaiting": False,
    }
    assert listed.json()[0]["transcription"] == expected
    assert read.json()["transcription"] == expected


async def test_server_records_verified_mime_not_the_clients_claim(
    client: AsyncClient, workspace_id: int
) -> None:
    """Multipart MIME is advisory; downloads use the server-owned type."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("notes.txt", b"research", "application/x-msdownload")},
    )
    document_id = created.json()["created"][0]["id"]

    downloaded = await client.get(
        f"/workspaces/{workspace_id}/documents/{document_id}/original"
    )

    assert downloaded.headers["content-type"].startswith("text/plain")


async def test_one_batch_cannot_hold_the_same_file_twice(
    client: AsyncClient, workspace_id: int
) -> None:
    """Nothing is committed mid-batch, so the check has to see uncommitted rows."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("report.pdf", b"%PDF-identical", "application/pdf")),
            ("files", ("copy.pdf", b"%PDF-identical", "application/pdf")),
        ],
    )

    assert len(response.json()["created"]) == 1
    assert [entry["filename"] for entry in response.json()["duplicates"]] == [
        "copy.pdf"
    ]


async def test_an_oversized_upload_is_refused_without_filling_the_disk(
    client: AsyncClient,
    workspace_id: int,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checked as it streams: a size read from the request would be the client's word."""
    monkeypatch.setattr(storage, "MAX_UPLOAD_BYTES", 8)

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("big.pdf", b"x" * 4096, "application/pdf")},
    )

    assert response.status_code == 413
    assert stored_files(data_dir) == []
    assert (await client.get(f"/workspaces/{workspace_id}/documents")).json() == []


async def test_a_filename_cannot_escape_the_data_directory(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """The client names the file; only its sanitized last part reaches a path."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("../../../../etc/report.txt", b"root:x:0:0", "text/plain")},
    )

    assert response.status_code == 201
    assert stored_files(data_dir) == [
        data_dir
        / "data"
        / "workspaces"
        / str(workspace_id)
        / "documents"
        / str(response.json()["created"][0]["id"])
        / "report.txt"
    ]


async def test_an_upload_leaves_no_temporary_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """The temporary file is written beside its destination, so a leak is in view."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert [path.name for path in stored_files(data_dir)] == ["report.pdf"]


async def test_the_original_is_served_back(
    client: AsyncClient, workspace_id: int
) -> None:
    """The documents view links to the file the user actually gave us."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7 fake", "application/pdf")},
    )
    document_id = created.json()["created"][0]["id"]

    response = await client.get(
        f"/workspaces/{workspace_id}/documents/{document_id}/original"
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 fake"
    # Never inline: a stored html file would otherwise run its script here.
    assert "attachment" in response.headers["content-disposition"]


async def test_a_note_has_no_original_to_serve(
    client: AsyncClient, workspace_id: int
) -> None:
    """Notes were typed, not uploaded, and the route must say so rather than 500."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "agreed to ship"},
    )

    response = await client.get(
        f"/workspaces/{workspace_id}/documents/{created.json()['id']}/original"
    )

    assert response.status_code == 404


async def test_a_deleted_document_takes_its_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """Left behind, the bytes are unreachable and never freed."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )

    await client.delete(
        f"/workspaces/{workspace_id}/documents/{created.json()['created'][0]['id']}"
    )

    assert stored_files(data_dir) == []


async def test_an_upload_given_a_deleted_documents_id_starts_with_its_folder_empty(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """SQLite gives the highest id out again, and a delete leaves a file it cannot
    remove, as one held open on Windows: the new document must not read it."""
    first = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )
    deleted = first.json()["created"][0]["id"]
    await client.delete(f"/workspaces/{workspace_id}/documents/{deleted}")
    left = get_storage_settings().document_dir(workspace_id, deleted)
    (left / "figures").mkdir(parents=True)
    (left / "report.pdf").write_bytes(b"%PDF-1.7")
    (left / "figures" / "figures.json").write_text(
        '{"version": 1, "figures": []}', encoding="utf-8"
    )

    second = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("budget.pdf", b"%PDF-1.7 budget", "application/pdf")},
    )

    assert second.json()["created"][0]["id"] == deleted
    assert [path.name for path in stored_files(data_dir)] == ["budget.pdf"]


async def test_a_deleted_workspace_takes_every_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """One tree per workspace, so this is a single call rather than one per document."""
    for name in ("a.pdf", "b.pdf"):
        await client.post(
            f"/workspaces/{workspace_id}/documents/upload",
            files={"files": (name, b"%PDF-" + name.encode(), "application/pdf")},
        )

    await client.delete(f"/workspaces/{workspace_id}")

    assert stored_files(data_dir) == []


async def test_a_failed_document_can_be_retried(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """Re-uploading is refused as a duplicate, so this is the only way back."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )
    document_id = created.json()["created"][0]["id"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE documents SET status = 'failed', error_message = 'model server down' "
                "WHERE id = :id"
            ),
            {"id": document_id},
        )
    ingest_queue.flush()

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/retry"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["error_message"] is None
    assert [job.args for job in ingest_queue.pending()] == [(document_id,)]


async def test_a_pending_document_can_be_cancelled(
    client: AsyncClient, workspace_id: int
) -> None:
    """Cancel drops the queued ingest so the worker never picks it up."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )
    document_id = created.json()["created"][0]["id"]
    assert ingest_queue.pending()

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["error_message"] is None
    task = ingest_queue.pending()[0]
    assert ingest_queue.is_revoked(task)


async def test_cancelling_a_recording_that_gave_way_drops_its_decoded_audio(
    client: AsyncClient, workspace_id: int
) -> None:
    """No run of its job is left to clear the 115 MB an hour it decoded; the
    windows written stay, so a retry carries on from them."""
    tones = Path(__file__).resolve().parents[2] / "fixtures" / "audio"
    uploaded = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("lecture.flac", (tones / "tone.flac").read_bytes(), "")},
    )
    recording = uploaded.json()["created"][0]["id"]
    work = work_files(get_storage_settings().document_dir(workspace_id, recording))
    work.folder.mkdir(parents=True)
    work.audio.write_bytes(b"\0" * 64)
    work.windows.write_text('{"n": 0}\n', encoding="utf-8")
    write_progress(work.progress, TranscriptionProgress(done_s=28.0, total_s=3480.0))

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{recording}/cancel"
    )

    assert response.status_code == 200
    assert (work.audio.exists(), work.progress.exists()) == (False, False)
    assert work.windows.exists()


async def test_a_ready_document_cannot_be_cancelled(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """Stopping a finished ingest would look like success and then vanish."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "note", "content": "x"},
    )
    document_id = created.json()["id"]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE documents SET status = 'ready' WHERE id = :id"),
            {"id": document_id},
        )

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/cancel"
    )

    assert response.status_code == 409


async def test_a_cancelled_document_can_be_retried(
    client: AsyncClient, workspace_id: int
) -> None:
    """Cancel is not delete: the bytes stay, and retry is the way back."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )
    document_id = created.json()["created"][0]["id"]
    await client.post(f"/workspaces/{workspace_id}/documents/{document_id}/cancel")
    ingest_queue.flush()

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/retry"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert [job.args for job in ingest_queue.pending()] == [(document_id,)]


async def test_only_a_failed_document_is_retried(
    client: AsyncClient, workspace_id: int
) -> None:
    """Requeueing one already in the queue would ingest it twice."""
    created = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/"
        f"{created.json()['created'][0]['id']}/retry"
    )

    assert response.status_code == 409
