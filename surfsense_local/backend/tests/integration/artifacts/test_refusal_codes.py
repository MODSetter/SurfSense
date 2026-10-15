"""A refused Studio job carries a code beside its sentence.

The interface shows its own line for a code (`studio-error-text.ts`) and the
backend's English for a refusal that has none, so a bare string here is a
sentence no translation reaches.
"""

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
    """Every route hangs off a workspace, and a summary needs a chat model."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN, provider="llamacpp", name="Qwen3-4B"
            )
        )
        session.commit()
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


def _note(engine: Engine, workspace_id: int, status: DocumentStatus) -> int:
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title="Facts",
            document_type=DocumentType.NOTE,
            status=status,
            content="Saturn has rings.",
        )
        session.add(document)
        session.commit()
        return document.id


async def _summary(client: AsyncClient, workspace_id: int, source_id: int) -> int:
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


def _finish(engine: Engine, artifact_id: int) -> None:
    """As if the worker had run it; the queue is emptied of its job."""
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        artifact.document.status = DocumentStatus.READY
        session.commit()
    studio_queue.flush()


async def test_regenerating_a_job_that_is_still_running(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """A job still queued is not run a second time."""
    artifact_id = await _summary(
        client, workspace_id, _note(engine, workspace_id, DocumentStatus.READY)
    )

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert again.status_code == 409
    assert again.json()["detail"] == {
        "message": "already generating",
        "code": "already_generating",
    }


async def test_cancelling_a_job_that_has_finished(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """There is nothing left to stop."""
    artifact_id = await _summary(
        client, workspace_id, _note(engine, workspace_id, DocumentStatus.READY)
    )
    _finish(engine, artifact_id)

    cancelled = await client.post(f"/artifacts/{artifact_id}/cancel")

    assert cancelled.status_code == 409
    assert cancelled.json()["detail"] == {
        "message": "nothing is running",
        "code": "nothing_running",
    }


@pytest.mark.parametrize(
    "sources",
    [
        {"document_ids": []},
        {"source_scope": {"all": True}},  # a workspace with no source in it
    ],
)
async def test_a_job_with_no_source(
    client: AsyncClient, workspace_id: int, sources: dict
) -> None:
    """One code for both ways of choosing nothing: no ids, and an empty scope."""
    refused = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", **sources},
    )

    assert refused.status_code == 422
    assert refused.json()["detail"] == {
        "message": "pick at least one source",
        "code": "no_sources",
    }


async def test_a_scope_whose_sources_are_all_still_indexing(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """Waiting helps here, so it is not the same refusal as choosing nothing."""
    _note(engine, workspace_id, DocumentStatus.PROCESSING)

    refused = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "source_scope": {"all": True}},
    )

    assert refused.status_code == 409
    assert refused.json()["detail"] == {
        "message": "the chosen sources are still indexing",
        "code": "sources_indexing",
    }


async def test_regenerating_when_every_source_is_gone(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """The sources it was made from were all deleted since."""
    source_id = _note(engine, workspace_id, DocumentStatus.READY)
    artifact_id = await _summary(client, workspace_id, source_id)
    _finish(engine, artifact_id)
    await client.delete(f"/workspaces/{workspace_id}/documents/{source_id}")

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert again.status_code == 409
    assert again.json()["detail"] == {
        "message": "None of this artifact's sources are left.",
        "code": "sources_gone",
    }
