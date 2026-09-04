"""Uploading a file: what lands in the row, on disk, and in the queue."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, text

from modules.documents import storage
from shared.queue import huey

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
    assert [path.name for path in stored] == ["original.pdf"]
    assert stored[0].read_bytes() == b"%PDF-1.7 fake"

    assert [(job.name, job.args) for job in huey.pending()] == [
        ("ingest_document", (created[0]["id"],))
    ]


async def test_the_same_bytes_are_not_ingested_twice(
    client: AsyncClient, workspace_id: int
) -> None:
    """Embedding a document twice doubles the work and splits its citations."""
    first = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"identical", "application/pdf")},
    )
    second = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("renamed.pdf", b"identical", "application/pdf")},
    )

    assert second.status_code == 201
    assert second.json()["created"] == []
    assert second.json()["duplicates"] == [
        {"filename": "renamed.pdf", "document_id": first.json()["created"][0]["id"]}
    ]


async def test_a_different_file_of_the_same_name_is_kept(
    client: AsyncClient, workspace_id: int
) -> None:
    """Cloud keys dedup on the filename, so report.pdf could be uploaded once, ever."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"january", "application/pdf")},
    )
    second = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"february", "application/pdf")},
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
            files={"files": ("report.pdf", b"shared", "application/pdf")},
        )

        assert len(response.json()["created"]) == 1


async def test_a_batch_is_split_rather_than_rejected(
    client: AsyncClient, workspace_id: int
) -> None:
    """A dropped folder holding one known file must not lose the other three."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("old.pdf", b"seen before", "application/pdf")},
    )

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("old.pdf", b"seen before", "application/pdf")),
            ("files", ("new.pdf", b"never seen", "application/pdf")),
        ],
    )

    assert [document["title"] for document in response.json()["created"]] == ["new.pdf"]
    assert [entry["filename"] for entry in response.json()["duplicates"]] == ["old.pdf"]


async def test_one_batch_cannot_hold_the_same_file_twice(
    client: AsyncClient, workspace_id: int
) -> None:
    """Nothing is committed mid-batch, so the check has to see uncommitted rows."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files=[
            ("files", ("report.pdf", b"identical", "application/pdf")),
            ("files", ("copy.pdf", b"identical", "application/pdf")),
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
    """The client names the file; only its extension is allowed near a path."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("../../../../etc/passwd", b"root:x:0:0", "text/plain")},
    )

    assert response.status_code == 201
    assert stored_files(data_dir) == [
        data_dir
        / "data"
        / "workspaces"
        / str(workspace_id)
        / "documents"
        / str(response.json()["created"][0]["id"])
        / "original"
    ]


async def test_an_upload_leaves_no_temporary_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """The temporary file is written beside its destination, so a leak is in view."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert [path.name for path in stored_files(data_dir)] == ["original.pdf"]


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


async def test_a_deleted_workspace_takes_every_file(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """One tree per workspace, so this is a single call rather than one per document."""
    for name in ("a.pdf", "b.pdf"):
        await client.post(
            f"/workspaces/{workspace_id}/documents/upload",
            files={"files": (name, name.encode(), "application/pdf")},
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
    huey.flush()

    response = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/retry"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["error_message"] is None
    assert [job.args for job in huey.pending()] == [(document_id,)]


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
