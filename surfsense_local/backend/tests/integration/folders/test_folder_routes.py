"""Library folders over HTTP: make, rename, move, delete, and file sources in them."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, func, select

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def _folders(client: AsyncClient, workspace_id: int) -> list[dict]:
    listed = await client.get(f"/workspaces/{workspace_id}/folders")
    assert listed.status_code == 200, listed.text
    return listed.json()


async def _root(client: AsyncClient, workspace_id: int) -> dict:
    (root,) = [
        f for f in await _folders(client, workspace_id) if f["parent_id"] is None
    ]
    return root


async def _make(
    client: AsyncClient, workspace_id: int, name: str, parent_id: int | None = None
) -> dict:
    made = await client.post(
        f"/workspaces/{workspace_id}/folders",
        json={"parent_id": parent_id, "name": name},
    )
    assert made.status_code == 201, made.text
    return made.json()


async def _note(
    client: AsyncClient, workspace_id: int, title: str, folder_id: int | None = None
) -> dict:
    body: dict = {"title": title, "content": f"{title} body"}
    if folder_id is not None:
        body["folder_id"] = folder_id
    made = await client.post(f"/workspaces/{workspace_id}/documents", json=body)
    assert made.status_code == 201, made.text
    return made.json()


async def test_a_new_workspace_has_a_library_with_its_own_root_folder(
    client: AsyncClient, workspace_id: int
) -> None:
    """A new workspace has a library with its own root folder."""
    folders = await _folders(client, workspace_id)

    assert len(folders) == 1
    assert folders[0]["name"] == "Library"
    assert folders[0]["parent_id"] is None


async def test_a_folder_made_with_no_parent_goes_into_the_library(
    client: AsyncClient, workspace_id: int
) -> None:
    """A folder made with no parent goes into the library."""
    root = await _root(client, workspace_id)

    made = await _make(client, workspace_id, "  Contracts  ")

    assert made["parent_id"] == root["id"]
    assert made["name"] == "Contracts"
    assert made["role"] is None
    assert {f["id"] for f in await _folders(client, workspace_id)} == {
        root["id"],
        made["id"],
    }


async def test_names_are_unique_per_folder_whatever_their_case(
    client: AsyncClient, workspace_id: int
) -> None:
    """SQLite's NOCASE folds ASCII only, so the key is folded in Python."""
    first = await _make(client, workspace_id, "Été")

    clash = await client.post(
        f"/workspaces/{workspace_id}/folders", json={"parent_id": None, "name": "ÉTÉ"}
    )
    elsewhere = await _make(client, workspace_id, "ÉTÉ", first["id"])

    assert clash.status_code == 409
    assert elsewhere["parent_id"] == first["id"]


async def test_eight_levels_are_allowed_and_a_ninth_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """Eight levels are allowed and a ninth is refused."""
    parent = None
    for level in range(1, 9):
        parent = (await _make(client, workspace_id, f"L{level}", parent))["id"]

    ninth = await client.post(
        f"/workspaces/{workspace_id}/folders", json={"parent_id": parent, "name": "L9"}
    )

    assert ninth.status_code == 400


async def test_a_folder_cannot_move_into_itself_or_below_itself(
    client: AsyncClient, workspace_id: int
) -> None:
    """A folder cannot move into itself or below itself."""
    outer = await _make(client, workspace_id, "Outer")
    inner = await _make(client, workspace_id, "Inner", outer["id"])

    into_child = await client.patch(
        f"/workspaces/{workspace_id}/folders/{outer['id']}",
        json={"parent_id": inner["id"]},
    )
    into_self = await client.patch(
        f"/workspaces/{workspace_id}/folders/{outer['id']}",
        json={"parent_id": outer["id"]},
    )

    assert into_child.status_code == 400
    assert into_self.status_code == 400


async def test_a_move_that_would_sink_a_subtree_past_the_cap_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """A move that would sink a subtree past the cap is refused."""
    deep = None
    for level in range(1, 8):
        deep = (await _make(client, workspace_id, f"D{level}", deep))["id"]
    tree = await _make(client, workspace_id, "Tree")
    await _make(client, workspace_id, "Branch", tree["id"])

    sunk = await client.patch(
        f"/workspaces/{workspace_id}/folders/{tree['id']}", json={"parent_id": deep}
    )

    assert sunk.status_code == 400


async def test_a_folder_can_be_renamed_moved_and_given_a_role(
    client: AsyncClient, workspace_id: int
) -> None:
    """A folder can be renamed moved and given a role."""
    target = await _make(client, workspace_id, "Clients")
    folder = await _make(client, workspace_id, "Acme")

    changed = await client.patch(
        f"/workspaces/{workspace_id}/folders/{folder['id']}",
        json={"name": "Acme Ltd", "parent_id": target["id"], "role": "evidence"},
    )
    cleared = await client.patch(
        f"/workspaces/{workspace_id}/folders/{folder['id']}", json={"role": None}
    )
    unknown = await client.patch(
        f"/workspaces/{workspace_id}/folders/{folder['id']}", json={"role": "boss"}
    )

    assert changed.status_code == 200
    assert changed.json()["role"] == "evidence"
    assert changed.json()["name"] == "Acme Ltd"
    assert changed.json()["parent_id"] == target["id"]
    assert cleared.json()["role"] is None
    assert cleared.json()["name"] == "Acme Ltd"
    assert unknown.status_code == 422


async def test_a_rename_onto_a_siblings_name_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """A rename onto a siblings name is refused."""
    await _make(client, workspace_id, "Taken")
    folder = await _make(client, workspace_id, "Free")

    clash = await client.patch(
        f"/workspaces/{workspace_id}/folders/{folder['id']}", json={"name": "taken"}
    )

    assert clash.status_code == 409


async def test_the_librarys_own_folder_cannot_be_renamed_moved_or_deleted(
    client: AsyncClient, workspace_id: int
) -> None:
    """The librarys own folder cannot be renamed moved or deleted."""
    root = await _root(client, workspace_id)
    other = await _make(client, workspace_id, "Other")

    renamed = await client.patch(
        f"/workspaces/{workspace_id}/folders/{root['id']}", json={"name": "Mine"}
    )
    moved = await client.patch(
        f"/workspaces/{workspace_id}/folders/{root['id']}",
        json={"parent_id": other["id"]},
    )
    deleted = await client.delete(f"/workspaces/{workspace_id}/folders/{root['id']}")

    assert (renamed.status_code, moved.status_code, deleted.status_code) == (
        409,
        409,
        409,
    )


async def test_another_workspaces_folder_is_not_found(
    client: AsyncClient, workspace_id: int
) -> None:
    """Another workspaces folder is not found."""
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    theirs = await _make(client, other["id"], "Theirs")

    under = await client.post(
        f"/workspaces/{workspace_id}/folders",
        json={"parent_id": theirs["id"], "name": "x"},
    )
    renamed = await client.patch(
        f"/workspaces/{workspace_id}/folders/{theirs['id']}", json={"name": "y"}
    )

    assert under.status_code == 404
    assert renamed.status_code == 404


async def test_a_note_is_filed_in_the_library_or_the_folder_it_names(
    client: AsyncClient, workspace_id: int
) -> None:
    """A note is filed in the library or the folder it names."""
    root = await _root(client, workspace_id)
    folder = await _make(client, workspace_id, "Drafts")

    loose = await _note(client, workspace_id, "Loose")
    filed = await _note(client, workspace_id, "Filed", folder["id"])

    assert loose["folder_id"] == root["id"]
    assert filed["folder_id"] == folder["id"]
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert {d["title"]: d["folder_id"] for d in listed} == {
        "Loose": root["id"],
        "Filed": folder["id"],
    }


async def test_documents_move_between_folders_and_twins_are_skipped(
    client: AsyncClient, workspace_id: int
) -> None:
    """Dedup is per folder: a file whose bytes already sit in the target stays put."""
    folder = await _make(client, workspace_id, "Archive")
    uploaded = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("a.pdf", b"%PDF-same", "application/pdf")},
    )
    copy = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        data={"folder_id": str(folder["id"])},
        files={"files": ("b.pdf", b"%PDF-same", "application/pdf")},
    )
    note = await _note(client, workspace_id, "Plan")
    twin_id = uploaded.json()["created"][0]["id"]
    assert copy.json()["created"][0]["folder_id"] == folder["id"]

    moved = await client.post(
        f"/workspaces/{workspace_id}/documents/move",
        json={"document_ids": [twin_id, note["id"]], "folder_id": folder["id"]},
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["moved"] == [note["id"]]
    assert moved.json()["skipped"] == [
        {
            "document_id": twin_id,
            "reason": "duplicate",
            "duplicate_of": copy.json()["created"][0]["id"],
        }
    ]
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert {d["id"]: d["folder_id"] for d in listed}[note["id"]] == folder["id"]


async def test_a_move_naming_another_workspaces_document_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """A move naming another workspaces document is refused."""
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    theirs = await _note(client, other["id"], "Theirs")
    folder = await _make(client, workspace_id, "Mine")

    refused = await client.post(
        f"/workspaces/{workspace_id}/documents/move",
        json={"document_ids": [theirs["id"]], "folder_id": folder["id"]},
    )

    assert refused.status_code == 422


async def test_deleting_a_folder_counts_then_removes_its_whole_subtree(
    client: AsyncClient,
    workspace_id: int,
    engine: Engine,
    data_dir: Path,
    real_model: object,
) -> None:
    """Deleting a folder counts then removes its whole subtree."""
    root = await _root(client, workspace_id)
    folder = await _make(client, workspace_id, "Old")
    sub = await _make(client, workspace_id, "Older", folder["id"])
    kept = await _note(client, workspace_id, "Kept")
    first = await _note(client, workspace_id, "First", folder["id"])
    upload = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        data={"folder_id": str(sub["id"])},
        files={"files": ("deep.pdf", b"%PDF-deep", "application/pdf")},
    )
    deep_id = upload.json()["created"][0]["id"]
    run(first["id"])

    summary = await client.get(
        f"/workspaces/{workspace_id}/folders/{folder['id']}/summary"
    )
    deleted = await client.delete(f"/workspaces/{workspace_id}/folders/{folder['id']}")

    assert summary.json() == {"folders": 1, "sources": 2, "artifacts": 0}
    assert deleted.status_code == 204
    assert [f["id"] for f in await _folders(client, workspace_id)] == [root["id"]]
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert [d["id"] for d in listed] == [kept["id"]]
    documents_dir = data_dir / "data" / "workspaces" / str(workspace_id)
    assert not (documents_dir / "documents" / str(deep_id)).exists()
    with create_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0


async def test_a_folder_holding_a_source_being_read_waits(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """A folder holding a source being read waits."""
    folder = await _make(client, workspace_id, "Busy")
    note = await _note(client, workspace_id, "Busy note", folder["id"])
    with create_session_factory(engine)() as session:
        document = session.get(Document, note["id"])
        assert document is not None
        document.status = DocumentStatus.PROCESSING
        session.commit()

    refused = await client.delete(f"/workspaces/{workspace_id}/folders/{folder['id']}")

    assert refused.status_code == 409
    assert len(await _folders(client, workspace_id)) == 2


async def test_a_read_queued_in_a_folder_being_deleted_never_starts(
    client: AsyncClient,
    workspace_id: int,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued read the worker reaches mid-delete is not left behind unfiled."""
    from modules.folders import delete_folder as deleting
    from worker.jobs import begin_job

    folder = await _make(client, workspace_id, "Copy")
    queued = await _note(client, workspace_id, "Queued", folder["id"])
    next_batch = deleting._next_batch
    started: list[bool] = []

    def worker_reaches_it_first(session, folders):
        if not started:
            with create_session_factory(engine)() as worker:
                document = worker.get(Document, queued["id"])
                assert document is not None
                started.append(begin_job(worker, document))
        return next_batch(session, folders)

    monkeypatch.setattr(deleting, "_next_batch", worker_reaches_it_first)

    deleted = await client.delete(f"/workspaces/{workspace_id}/folders/{folder['id']}")

    assert deleted.status_code == 204
    assert started == [False]
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert listed == []


async def test_cancelling_a_folder_stops_every_queued_read_below_it(
    client: AsyncClient, workspace_id: int
) -> None:
    """Cancelling a folder stops every queued read below it."""
    folder = await _make(client, workspace_id, "Copy")
    sub = await _make(client, workspace_id, "Deeper", folder["id"])
    first = await _note(client, workspace_id, "First", folder["id"])
    second = await _note(client, workspace_id, "Second", sub["id"])
    elsewhere = await _note(client, workspace_id, "Elsewhere")

    cancelled = await client.post(
        f"/workspaces/{workspace_id}/folders/{folder['id']}/cancel"
    )

    assert cancelled.status_code == 200
    assert sorted(cancelled.json()["cancelled"]) == sorted([first["id"], second["id"]])
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert {d["id"]: d["status"] for d in listed} == {
        first["id"]: "cancelled",
        second["id"]: "cancelled",
        elsewhere["id"]: "pending",
    }


async def test_every_source_can_be_listed_page_by_page(
    client: AsyncClient, workspace_id: int, engine: Engine
) -> None:
    """The sources panel reads pages of 200 until one comes short."""
    with create_session_factory(engine)() as session:
        session.add_all(
            Document(
                workspace_id=workspace_id,
                title=f"n{n}",
                document_type="NOTE",
                content="x",
            )
            for n in range(260)
        )
        session.commit()

    seen: list[int] = []
    for offset in (0, 200):
        page = await client.get(
            f"/workspaces/{workspace_id}/documents",
            params={"limit": 200, "offset": offset},
        )
        seen += [d["id"] for d in page.json()]

    assert len(set(seen)) == 260
