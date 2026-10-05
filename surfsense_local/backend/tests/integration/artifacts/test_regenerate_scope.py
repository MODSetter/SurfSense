"""A Studio job takes a source scope, and regenerate re-resolves it."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from shared.db import create_session_factory
from shared.queue import studio_queue

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient, engine: Engine) -> int:
    """Every route hangs off a workspace, so every test needs one."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN, provider="llamacpp", name="Qwen3-4B"
            )
        )
        session.commit()
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


def _ready_note(engine: Engine, workspace_id: int, title: str = "Facts") -> int:
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title=title,
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content="Saturn has rings.",
        )
        session.add(document)
        session.commit()
        return document.id


def _metadata(engine: Engine, artifact_id: int) -> dict:
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        return dict(artifact.artifact_metadata or {})


def _finish(engine: Engine, artifact_id: int) -> None:
    """As if the worker had run it; the queue is emptied of its job."""
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        artifact.document.status = DocumentStatus.READY
        session.commit()
    studio_queue.flush()


async def test_a_job_resolves_its_scope_and_records_it(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """A job resolves its scope and records it."""
    first = _ready_note(engine, workspace_id)
    second = _ready_note(engine, workspace_id)

    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={
            "format": "summary",
            "source_scope": {"all": True, "excluded_document_ids": [second]},
        },
    )

    assert created.status_code == 201, created.text
    metadata = _metadata(engine, created.json()["id"])
    assert metadata["source_document_ids"] == [first]
    assert metadata["source_scope"]["excluded_document_ids"] == [second]


async def test_a_scope_with_nothing_ready_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """A scope with nothing ready is refused."""
    refused = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "source_scope": {"all": True}},
    )

    assert refused.status_code == 422


async def test_regenerate_uses_a_file_added_after_the_first_run(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """A ticked scope is dynamic; the artifact itself never grounds itself."""
    first = _ready_note(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "source_scope": {"all": True}},
    )
    artifact_id = created.json()["id"]
    _finish(engine, artifact_id)
    later = _ready_note(engine, workspace_id, "Later")

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert again.status_code == 202
    assert _metadata(engine, artifact_id)["source_document_ids"] == [first, later]


async def test_an_artifact_made_from_a_list_replays_its_list(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """An artifact made from a list replays its list."""
    first = _ready_note(engine, workspace_id)
    _ready_note(engine, workspace_id, "Unchosen")
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [first]},
    )
    artifact_id = created.json()["id"]
    _finish(engine, artifact_id)

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert again.status_code == 202
    assert _metadata(engine, artifact_id)["source_document_ids"] == [first]


async def test_regenerate_with_no_sources_left_says_so(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """Regenerate with no sources left says so."""
    first = _ready_note(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [first]},
    )
    artifact_id = created.json()["id"]
    _finish(engine, artifact_id)
    await client.delete(f"/workspaces/{workspace_id}/documents/{first}")

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert again.status_code == 409
    assert again.json()["detail"] == "None of this artifact's sources are left."
