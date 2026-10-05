"""A folder delete the app stopped partway through is finished at the next start."""

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, select

from api.main import create_app, lifespan
from modules.documents.models import Document, DocumentStatus
from modules.folders import delete_folder as deleting
from modules.folders.finish_deletes import finish_interrupted_deletes
from modules.folders.models import Folder, FolderState
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


class AppStoppedError(Exception):
    """The process dying between two batches of a delete."""


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Folders hang off a workspace."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def _make(
    client: AsyncClient, workspace_id: int, name: str, parent_id: int | None = None
) -> int:
    made = await client.post(
        f"/workspaces/{workspace_id}/folders",
        json={"parent_id": parent_id, "name": name},
    )
    assert made.status_code == 201, made.text
    return int(made.json()["id"])


async def _note(
    client: AsyncClient, workspace_id: int, title: str, folder_id: int | None = None
) -> int:
    body: dict = {"title": title, "content": f"{title} body"}
    if folder_id is not None:
        body["folder_id"] = folder_id
    made = await client.post(f"/workspaces/{workspace_id}/documents", json=body)
    assert made.status_code == 201, made.text
    return int(made.json()["id"])


async def _stop_partway_through_a_delete(
    client: AsyncClient,
    workspace_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, int, int]:
    """A folder with a subfolder, one source in each, deleted until the first batch."""
    folder = await _make(client, workspace_id, "Old")
    sub = await _make(client, workspace_id, "Older", folder)
    await _note(client, workspace_id, "First", folder)
    await _note(client, workspace_id, "Deep", sub)
    kept = await _note(client, workspace_id, "Kept")

    def stop(*_: object) -> list[int]:
        raise AppStoppedError

    with monkeypatch.context() as patch:
        patch.setattr(deleting, "_next_batch", stop)
        with pytest.raises(AppStoppedError):
            await client.delete(f"/workspaces/{workspace_id}/folders/{folder}")
    return folder, sub, kept


def _left(engine: Engine) -> tuple[list[FolderState], list[int]]:
    with create_session_factory(engine)() as session:
        states = list(
            session.scalars(select(Folder.state).where(Folder.parent_id.is_not(None)))
        )
        documents = list(session.scalars(select(Document.id).order_by(Document.id)))
    return states, documents


async def test_a_delete_stopped_partway_is_finished_and_finishing_twice_is_harmless(
    client: AsyncClient,
    workspace_id: int,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without this, the subtree stays `deleting` forever and its sources in no scope."""
    _, _, kept = await _stop_partway_through_a_delete(client, workspace_id, monkeypatch)
    assert _left(engine)[0] == [FolderState.DELETING, FolderState.DELETING]

    finish_interrupted_deletes(create_session_factory(engine))
    finish_interrupted_deletes(create_session_factory(engine))

    assert _left(engine) == ([], [kept])


async def test_a_source_still_being_read_keeps_its_folder_until_a_later_start(
    client: AsyncClient,
    workspace_id: int,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A folder cannot go while a source in it does; the rest goes now."""
    folder, sub, kept = await _stop_partway_through_a_delete(
        client, workspace_id, monkeypatch
    )
    factory = create_session_factory(engine)
    with factory() as session:
        busy = session.scalars(select(Document).where(Document.folder_id == sub)).one()
        busy.status = DocumentStatus.PROCESSING
        session.commit()
        busy_id = busy.id

    finish_interrupted_deletes(factory)

    assert _left(engine) == (
        [FolderState.DELETING, FolderState.DELETING],
        [busy_id, kept],
    )
    with factory() as session:
        session.get_one(Document, busy_id).status = DocumentStatus.FAILED
        session.commit()

    finish_interrupted_deletes(factory)

    assert _left(engine) == ([], [kept])
    with factory() as session:
        assert session.get(Folder, folder) is None


async def test_the_api_finishes_them_when_it_starts(
    client: AsyncClient,
    workspace_id: int,
    engine: Engine,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Off the start-up path: a large subtree must not hold /health back."""
    _, _, kept = await _stop_partway_through_a_delete(client, workspace_id, monkeypatch)
    monkeypatch.setattr("api.main._warm_catalog", lambda _factory: None)

    async with lifespan(create_app()):
        for _ in range(100):
            if _left(engine)[0] == []:
                break
            await asyncio.sleep(0.05)

    assert _left(engine) == ([], [kept])
