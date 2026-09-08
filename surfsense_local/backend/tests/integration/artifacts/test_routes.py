import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.models import ModelRole, SelectedModel
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every Studio route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


@pytest.fixture
def choose_model(engine: Engine) -> None:
    """A generation model must be selected before a job can run."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(role=ModelRole.GENERATION, provider="ollama", name="qwen3:4b")
        )
        session.commit()


def make_ready_source(engine: Engine, workspace_id: int) -> int:
    """A source has to be indexed before it can feed a job."""
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title="Facts",
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content="Saturn has rings.",
        )
        session.add(document)
        session.commit()
        return document.id


async def test_formats_lists_summary_as_available(
    client: AsyncClient, workspace_id: int
) -> None:
    """The picker renders from this; summary needs no key, so it is usable."""
    response = await client.get(f"/workspaces/{workspace_id}/studio/formats")

    assert response.status_code == 200
    summary = next(f for f in response.json() if f["key"] == "summary")
    assert summary["available"] is True
    assert summary["requires_key"] is False


async def test_a_job_creates_a_pending_artifact(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """The row is written and enqueued; the worker (absent here) would finish it."""
    source_id = make_ready_source(engine, workspace_id)

    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["format"] == "summary"
    assert body["status"] == "pending"

    listed = await client.get(f"/workspaces/{workspace_id}/artifacts")
    assert [a["id"] for a in listed.json()] == [body["id"]]

    detail = await client.get(f"/artifacts/{body['id']}")
    assert detail.json()["content"] is None
    assert detail.json()["files"] == []


async def test_a_job_needs_a_generation_model(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """Fail fast at submit, not as a failed job the user has to inspect."""
    source_id = make_ready_source(engine, workspace_id)

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )

    assert response.status_code == 409


async def test_a_job_rejects_an_unknown_format(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """A format with no builder is refused at submit, not enqueued to fail."""
    source_id = make_ready_source(engine, workspace_id)

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "hologram", "document_ids": [source_id]},
    )

    assert response.status_code == 422


async def test_a_job_rejects_a_source_from_another_workspace(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """One workspace's id must not pull another's document into a job."""
    other = await client.post("/workspaces", json={"name": "Other"})
    foreign_id = make_ready_source(engine, int(other.json()["id"]))

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [foreign_id]},
    )

    assert response.status_code == 422


async def test_a_job_waits_for_a_source_to_index(
    client: AsyncClient, workspace_id: int, choose_model: None
) -> None:
    """A pending note is not searchable yet, so it cannot ground a summary."""
    note = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Draft", "content": "unindexed"},
    )

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [int(note.json()["id"])]},
    )

    assert response.status_code == 409


async def test_an_artifact_can_be_deleted(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """Deleting the artifact removes its row; the detail route then 404s."""
    source_id = make_ready_source(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    artifact_id = created.json()["id"]

    deleted = await client.delete(f"/artifacts/{artifact_id}")
    assert deleted.status_code == 204

    gone = await client.get(f"/artifacts/{artifact_id}")
    assert gone.status_code == 404
