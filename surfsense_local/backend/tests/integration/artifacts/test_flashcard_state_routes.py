"""The flashcard-state routes: a real deck artifact on disk, driven over HTTP."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_search_settings
from shared.db import create_session_factory
from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.shared import persist

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """persist() indexes the deck's markdown; stand in for the embedder so
    these tests don't need the bundled model on disk (see
    tests/integration/worker/conftest.py's identical fixture)."""
    width = get_search_settings().embedding_dimension

    def embed(texts: list[str]) -> list[list[float]]:
        return [[float(len(text) % 97)] * width for text in texts]

    monkeypatch.setattr("worker.ingestion.embedding.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )


_MODEL_REPLY = (
    '{"title": "Cassini", "cards": ['
    '{"front": "Arrival year?", "back": "2004"},'
    '{"front": "Mission end year?", "back": "2017"},'
    '{"front": "Launch vehicle?", "back": "Titan IV"}'
    "]}"
)


def make_flashcards_artifact(session: Session) -> int:
    """A ready flashcards artifact with a real primary file on disk."""
    document = Document(
        workspace_id=1,
        title="Cassini Flashcards",
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()

    artifact = Artifact(document_id=document.id, workspace_id=1, format="flashcards")
    session.add(artifact)
    session.commit()

    built = flashcards.build(_MODEL_REPLY, [])
    persist.persist(session, artifact, document, built)
    session.commit()
    return artifact.id


@pytest.fixture
def workspace(engine: Engine) -> None:
    """Every artifact hangs off a workspace row."""
    from modules.workspaces.models import Workspace

    with create_session_factory(engine)() as session:
        session.add(Workspace(id=1, name="Saturn"))
        session.commit()


@pytest.fixture
def artifact_id(engine: Engine, workspace: None) -> int:
    """A ready flashcards artifact each test can drive over HTTP."""
    with create_session_factory(engine)() as session:
        return make_flashcards_artifact(session)


async def test_a_fresh_deck_starts_with_no_marks_and_canonical_order(
    client: AsyncClient, artifact_id: int
) -> None:
    """GET on a never-studied deck must synthesize an empty state rather
    than erroring or returning null."""
    response = await client.get(f"/artifacts/{artifact_id}")

    assert response.status_code == 200
    state = response.json()["flashcard_state"]
    assert state["generation"] == 1
    assert state["marks"] == {}
    assert state["order"] == [0, 1, 2]


async def test_marking_persists_across_requests(
    client: AsyncClient, artifact_id: int
) -> None:
    """A mark written by PUT must be readable back on the next GET — the
    whole point of persisting it instead of keeping it in memory."""
    put = await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/mark",
        json={"card_index": 0, "mark": "good"},
    )
    assert put.status_code == 200
    assert put.json()["marks"] == {"0": "good"}

    get = await client.get(f"/artifacts/{artifact_id}")
    assert get.json()["flashcard_state"]["marks"] == {"0": "good"}


async def test_a_card_index_outside_the_deck_is_rejected(
    client: AsyncClient, artifact_id: int
) -> None:
    """The HTTP layer must surface the pure function's bounds check as a
    409, not a 500 or a silently-accepted write."""
    response = await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/mark",
        json={"card_index": 99, "mark": "good"},
    )
    assert response.status_code == 409


async def test_shuffling_persists_the_new_order(
    client: AsyncClient, artifact_id: int
) -> None:
    """A shuffled order written by PUT must be readable back on GET."""
    response = await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/order",
        json={"order": [2, 0, 1]},
    )
    assert response.status_code == 200
    assert response.json()["order"] == [2, 0, 1]

    get = await client.get(f"/artifacts/{artifact_id}")
    assert get.json()["flashcard_state"]["order"] == [2, 0, 1]


async def test_an_incomplete_order_is_rejected(
    client: AsyncClient, artifact_id: int
) -> None:
    """The HTTP layer must surface the pure function's permutation check
    as a 422 rather than accepting a partial reorder."""
    response = await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/order",
        json={"order": [0, 1]},
    )
    assert response.status_code == 422


async def test_reset_clears_marks_but_keeps_the_shuffle_order(
    client: AsyncClient, artifact_id: int
) -> None:
    """A reset over HTTP must clear marks without reverting the order,
    same invariant as the pure function it wraps."""
    await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/mark",
        json={"card_index": 0, "mark": "again"},
    )
    await client.put(
        f"/artifacts/{artifact_id}/flashcard-state/order",
        json={"order": [2, 0, 1]},
    )

    reset = await client.put(f"/artifacts/{artifact_id}/flashcard-state/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["marks"] == {}
    assert body["order"] == [2, 0, 1]


async def test_a_non_flashcards_artifact_has_no_flashcard_state(
    client: AsyncClient, engine: Engine, workspace: None
) -> None:
    """flashcard_state must stay null for other formats, and mutating it
    must be refused rather than fabricating state for the wrong format."""
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=1,
            title="Overview",
            document_type=DocumentType.ARTIFACT,
            status=DocumentStatus.READY,
            content="# Overview",
        )
        session.add(document)
        session.flush()
        artifact = Artifact(document_id=document.id, workspace_id=1, format="summary")
        session.add(artifact)
        session.commit()
        summary_id = artifact.id

    response = await client.get(f"/artifacts/{summary_id}")
    assert response.json()["flashcard_state"] is None

    rejected = await client.put(
        f"/artifacts/{summary_id}/flashcard-state/mark",
        json={"card_index": 0, "mark": "good"},
    )
    assert rejected.status_code == 409
