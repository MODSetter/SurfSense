import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, func, insert, select

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace
from modules.workspaces.seed import ensure_default_workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


def test_seeding_adds_one_workspace_only_when_none_exist(engine: Engine) -> None:
    """Startup seeds a first workspace, but never a duplicate on later boots."""
    factory = create_session_factory(engine)
    with factory() as session:
        ensure_default_workspace(session)
        ensure_default_workspace(session)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Workspace)) == 1


async def test_a_created_workspace_is_listed(client: AsyncClient) -> None:
    """The first thing a new install does, and the shell's only phase-one call."""
    created = await client.post("/workspaces", json={"name": "Research"})

    assert created.status_code == 201
    assert created.json()["name"] == "Research"

    listed = await client.get("/workspaces")

    assert [workspace["id"] for workspace in listed.json()] == [created.json()["id"]]


async def test_workspaces_are_listed_oldest_first(client: AsyncClient) -> None:
    """A switcher that reorders itself on every poll is unusable."""
    for name in ("first", "second", "third"):
        await client.post("/workspaces", json={"name": name})

    listed = await client.get("/workspaces")

    assert [workspace["name"] for workspace in listed.json()] == [
        "first",
        "second",
        "third",
    ]


async def test_a_blank_name_is_rejected(client: AsyncClient) -> None:
    """Whitespace-only names render as an unclickable row in the switcher."""
    for name in ("", "   "):
        response = await client.post("/workspaces", json={"name": name})

        assert response.status_code == 422


async def test_a_rejected_workspace_is_not_stored(client: AsyncClient) -> None:
    """The session dependency must roll back what a failed request started."""
    await client.post("/workspaces", json={"name": ""})

    assert (await client.get("/workspaces")).json() == []


async def test_a_workspace_can_be_read_by_id(client: AsyncClient) -> None:
    """A deep link into a workspace has only its id to open from."""
    created = await client.post("/workspaces", json={"name": "Research"})

    response = await client.get(f"/workspaces/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json() == created.json()


async def test_a_workspace_can_be_renamed(client: AsyncClient) -> None:
    """A typo in the name of the first workspace should not be permanent."""
    created = await client.post("/workspaces", json={"name": "Reserch"})

    renamed = await client.patch(
        f"/workspaces/{created.json()['id']}", json={"name": "Research"}
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Research"
    assert (await client.get("/workspaces")).json()[0]["name"] == "Research"


async def test_a_rename_is_validated_like_a_create(client: AsyncClient) -> None:
    """Renaming is the other way to end up with a blank row in the switcher."""
    created = await client.post("/workspaces", json={"name": "Research"})

    response = await client.patch(
        f"/workspaces/{created.json()['id']}", json={"name": "   "}
    )

    assert response.status_code == 422


async def test_a_deleted_workspace_is_gone(client: AsyncClient) -> None:
    """Nothing else removes a workspace, so a mistyped one would be permanent."""
    created = await client.post("/workspaces", json={"name": "Research"})
    workspace_id = created.json()["id"]

    deleted = await client.delete(f"/workspaces/{workspace_id}")

    assert deleted.status_code == 204
    assert (await client.get(f"/workspaces/{workspace_id}")).status_code == 404
    assert (await client.get("/workspaces")).json() == []


async def test_deleting_a_workspace_takes_its_documents(
    client: AsyncClient, engine: Engine
) -> None:
    """Rows left behind would be unreachable: every read starts from a workspace."""
    created = await client.post("/workspaces", json={"name": "Research"})
    workspace_id = created.json()["id"]

    with engine.begin() as connection:
        connection.execute(
            insert(Document).values(
                id=1,
                workspace_id=workspace_id,
                title="x",
                document_type=DocumentType.FILE,
            )
        )
        connection.execute(
            insert(Chunk).values(document_id=1, position=0, content="hello")
        )

    await client.delete(f"/workspaces/{workspace_id}")

    with engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(Document)).scalar() == 0
        )
        assert connection.execute(select(func.count()).select_from(Chunk)).scalar() == 0


async def test_unknown_workspaces_are_not_found(client: AsyncClient) -> None:
    """Every route resolves the workspace the same way, so one guard covers them all."""
    assert (await client.get("/workspaces/404")).status_code == 404
    assert (
        await client.patch("/workspaces/404", json={"name": "x"})
    ).status_code == 404
    assert (await client.delete("/workspaces/404")).status_code == 404
