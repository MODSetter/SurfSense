"""Adding a whole folder: its tree arrives as folders, and copying it again adds nothing."""

import json
import re
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.documents.tasks import PRIORITY_BULK, PRIORITY_INTERACTIVE
from shared.queue import ingest_queue

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


def _files(names_and_bytes: list[tuple[str, bytes]]) -> list:
    """Each file under its own name, as a browser sends it: the path travels apart."""
    return [
        ("files", (re.split(r"[/\\]", name)[-1], content, "application/pdf"))
        for name, content in names_and_bytes
    ]


async def _upload(
    client: AsyncClient,
    workspace_id: int,
    entries: list[tuple[str, bytes]],
    folder_id: int | None = None,
):
    data = {"relative_paths": json.dumps([name for name, _ in entries])}
    if folder_id is not None:
        data["folder_id"] = str(folder_id)
    return await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        data=data,
        files=_files(entries),
    )


async def _chains(client: AsyncClient, workspace_id: int) -> dict[str, list[str]]:
    """Each document's title against its folder names below the Library."""
    folders = {
        f["id"]: f
        for f in (await client.get(f"/workspaces/{workspace_id}/folders")).json()
    }
    documents = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    chains = {}
    for document in documents:
        names, folder_id = [], document["folder_id"]
        while folders[folder_id]["parent_id"] is not None:
            names.append(folders[folder_id]["name"])
            folder_id = folders[folder_id]["parent_id"]
        chains[document["title"]] = list(reversed(names))
    return chains


async def test_relative_paths_build_the_folders_each_file_lands_in(
    client: AsyncClient, workspace_id: int
) -> None:
    """Relative paths build the folders each file lands in."""
    response = await _upload(
        client,
        workspace_id,
        [
            ("Research/a.pdf", b"%PDF-a"),
            ("Research/2024/b.pdf", b"%PDF-b"),
            ("Research/2024/c.pdf", b"%PDF-c"),
        ],
    )

    assert response.status_code == 201, response.text
    assert await _chains(client, workspace_id) == {
        "a.pdf": ["Research"],
        "b.pdf": ["Research", "2024"],
        "c.pdf": ["Research", "2024"],
    }


async def test_a_tree_deeper_than_eight_levels_arrives_whole(
    client: AsyncClient, workspace_id: int
) -> None:
    """A tree deeper than eight levels arrives whole."""
    deep = "/".join(f"L{n}" for n in range(1, 13))

    await _upload(client, workspace_id, [(f"{deep}/deep.pdf", b"%PDF-deep")])

    assert (await _chains(client, workspace_id))["deep.pdf"] == [
        *(f"L{n}" for n in range(1, 8)),
        " / ".join(f"L{n}" for n in range(8, 13)),
    ]


async def test_a_path_climbing_out_only_names_folders_inside_the_target(
    client: AsyncClient, workspace_id: int, data_dir: Path
) -> None:
    """`..`, roots and drive paths become folder names, never places on disk."""
    response = await _upload(
        client,
        workspace_id,
        [
            ("../../outside/a.pdf", b"%PDF-a"),
            ("/abs/b.pdf", b"%PDF-b"),
            (r"Win\..\..\c.pdf", b"%PDF-c"),
        ],
    )

    assert response.status_code == 201, response.text
    assert await _chains(client, workspace_id) == {
        "a.pdf": ["outside"],
        "b.pdf": ["abs"],
        "c.pdf": ["Win"],
    }
    assert not (data_dir / "outside").exists()


async def test_folders_an_upload_makes_are_announced_to_open_windows(
    client: AsyncClient, workspace_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another window's tree learns of the folders, not only of the files."""
    from modules.events.broker import EventBroker

    kinds: list[str] = []
    publish = EventBroker.publish

    def recording(self, notice):
        kinds.append(notice.kind)
        publish(self, notice)

    monkeypatch.setattr(EventBroker, "publish", recording)

    await _upload(client, workspace_id, [("Research/a.pdf", b"%PDF-a")])

    assert "folders" in kinds


async def test_a_folder_is_copied_whole_even_if_a_file_sits_elsewhere(
    client: AsyncClient, workspace_id: int
) -> None:
    """Dedup is per folder: a copied folder must not have holes in it."""
    await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("loose.pdf", b"%PDF-shared", "application/pdf")},
    )

    response = await _upload(
        client, workspace_id, [("Copy/inside.pdf", b"%PDF-shared")]
    )

    assert [d["title"] for d in response.json()["created"]] == ["inside.pdf"]
    assert response.json()["duplicates"] == []


async def test_copying_a_folder_again_reports_every_file_as_already_there(
    client: AsyncClient, workspace_id: int
) -> None:
    """Copying a folder again reports every file as already there."""
    entries = [("Research/a.pdf", b"%PDF-a"), ("Research/2024/b.pdf", b"%PDF-b")]
    first = await _upload(client, workspace_id, entries)
    created = {d["title"]: d for d in first.json()["created"]}

    again = await _upload(client, workspace_id, entries)

    assert again.json()["created"] == []
    assert again.json()["duplicates"] == [
        {
            "filename": "a.pdf",
            "document_id": created["a.pdf"]["id"],
            "folder_id": created["a.pdf"]["folder_id"],
        },
        {
            "filename": "b.pdf",
            "document_id": created["b.pdf"]["id"],
            "folder_id": created["b.pdf"]["folder_id"],
        },
    ]


async def test_a_folder_dropped_on_a_folder_lands_inside_it(
    client: AsyncClient, workspace_id: int
) -> None:
    """A folder dropped on a folder lands inside it."""
    target = await client.post(
        f"/workspaces/{workspace_id}/folders", json={"name": "Clients"}
    )

    await _upload(
        client, workspace_id, [("Acme/brief.pdf", b"%PDF-brief")], target.json()["id"]
    )

    assert (await _chains(client, workspace_id))["brief.pdf"] == ["Clients", "Acme"]


async def test_paths_must_match_the_files_one_for_one(
    client: AsyncClient, workspace_id: int
) -> None:
    """Paths must match the files one for one."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        data={"relative_paths": json.dumps(["a.pdf", "b.pdf"])},
        files=_files([("a.pdf", b"%PDF-a")]),
    )

    assert response.status_code == 422


async def test_an_upload_into_another_workspaces_folder_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """An upload into another workspaces folder is refused."""
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    theirs = await client.post(
        f"/workspaces/{other['id']}/folders", json={"name": "Theirs"}
    )

    response = await _upload(
        client, workspace_id, [("a.pdf", b"%PDF-a")], theirs.json()["id"]
    )

    assert response.status_code == 404


async def test_a_big_folder_queues_behind_a_single_upload(
    client: AsyncClient, workspace_id: int
) -> None:
    """A note written during a long copy is read first."""
    many = [(f"Big/{n}.pdf", f"%PDF-{n}".encode()) for n in range(21)]

    await _upload(client, workspace_id, many)
    await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Now", "content": "urgent"},
    )

    priorities = [job.priority for job in ingest_queue.pending()]
    assert priorities.count(PRIORITY_BULK) == 21
    assert priorities.count(PRIORITY_INTERACTIVE) == 1
