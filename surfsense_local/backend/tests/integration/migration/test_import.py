"""Importing a contract-3 export bundle: what the user gets back locally."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from httpx import AsyncClient, Response

from shared.queue import huey

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[5] / (
    "plans/community-local/contracts/export-sample"
)


def bundle(tmp_path: Path, manifest: dict | None = None) -> Path:
    """Zip the committed fixture, optionally with a manifest of the test's own."""
    path = tmp_path / "export.zip"
    with ZipFile(path, "w") as archive:
        if manifest is None:
            archive.write(SAMPLE / "manifest.json", "manifest.json")
        else:
            archive.writestr("manifest.json", json.dumps(manifest))
        for file in sorted(SAMPLE.rglob("*")):
            if file.is_file() and file.name != "manifest.json":
                archive.write(file, file.relative_to(SAMPLE).as_posix())
    return path


async def import_bundle(client: AsyncClient, path: Path) -> Response:
    """Post the file the way the renderer's picker will."""
    return await client.post(
        "/migration/import",
        files={"file": ("export.zip", path.read_bytes(), "application/zip")},
    )


async def test_each_exported_workspace_becomes_a_local_one(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A user with two cloud workspaces finds the same two after importing."""
    response = await import_bundle(client, bundle(tmp_path))

    assert response.status_code == 202
    listed = await client.get("/workspaces")
    assert [workspace["name"] for workspace in listed.json()] == ["Research", "Empty"]


async def test_listed_documents_are_created_pending_and_queued(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Only what the manifest lists: OKF index.md and log.md never become documents."""
    response = await import_bundle(client, bundle(tmp_path))
    research = response.json()["workspaces"][0]["id"]

    documents = (await client.get(f"/workspaces/{research}/documents")).json()
    assert sorted(document["title"] for document in documents) == [
        "Notes",
        "Notes",
        "Reading list",
        "Résumé de réunion",
        "index",
    ]
    assert {document["status"] for document in documents} == {"pending"}
    assert sorted(job.args[0] for job in huey.pending()) == sorted(
        document["id"] for document in documents
    )


async def test_threads_arrive_with_their_turns_and_sources_as_text(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Cloud citations cannot be clicked locally, so they are named in the answer."""
    response = await import_bundle(client, bundle(tmp_path))
    research = response.json()["workspaces"][0]["id"]

    threads = (await client.get(f"/workspaces/{research}/chat/threads")).json()
    assert sorted(thread["title"] for thread in threads) == [
        "Quick hello",
        "Why scale the dot product?",
    ]
    scaling = next(t for t in threads if t["title"].startswith("Why"))
    messages = (await client.get(f"/chat/threads/{scaling['id']}/messages")).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"]["text"].endswith("\n\nSources: Notes")
    assert messages[1]["content"]["citations"] == []


@pytest.mark.parametrize(
    "path",
    [
        "workspaces/12/documents/../../../etc/passwd",
        "/workspaces/12/documents/Notes.md",
        "workspaces/13/documents/Notes.md",
        "workspaces\\12\\documents\\Notes.md",
    ],
)
async def test_a_manifest_escaping_the_tree_is_rejected_before_anything_is_written(
    client: AsyncClient, tmp_path: Path, data_dir: Path, path: str
) -> None:
    """The manifest is untrusted input; one bad path fails the whole bundle."""
    manifest = json.loads((SAMPLE / "manifest.json").read_text())
    manifest["workspaces"][0]["documents"][0]["path"] = path

    response = await import_bundle(client, bundle(tmp_path, manifest))

    assert response.status_code == 422
    assert (await client.get("/workspaces")).json() == []
    assert not (data_dir / "data").exists()


async def test_other_formats_and_non_bundles_are_refused(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Only surfsense-export/1; a future format needs a new reader, not a guess."""
    manifest = json.loads((SAMPLE / "manifest.json").read_text())
    manifest["format"] = "surfsense-export/2"
    other_format = await import_bundle(client, bundle(tmp_path, manifest))

    not_a_zip = tmp_path / "notes.md"
    not_a_zip.write_text("# just a file")
    not_a_bundle = await import_bundle(client, not_a_zip)

    assert other_format.status_code == 422
    assert not_a_bundle.status_code == 422
    assert (await client.get("/workspaces")).json() == []


async def test_importing_the_same_bundle_twice_adds_nothing(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Quitting mid-import and running it again must not double the account."""
    first = await import_bundle(client, bundle(tmp_path))
    second = await import_bundle(client, bundle(tmp_path))
    research = first.json()["workspaces"][0]["id"]

    assert second.json() == first.json()
    assert len((await client.get("/workspaces")).json()) == 2
    assert len((await client.get(f"/workspaces/{research}/documents")).json()) == 5
    assert len((await client.get(f"/workspaces/{research}/chat/threads")).json()) == 2
