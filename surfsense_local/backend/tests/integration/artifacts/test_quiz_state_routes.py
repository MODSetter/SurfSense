"""The quiz-state routes: a real quiz artifact on disk, driven over HTTP."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_search_settings
from shared.db import create_session_factory
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.shared import persist

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """persist() indexes the quiz's markdown; stand in for the embedder so
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
    '{"title": "Cassini", "questions": ['
    '{"question": "Arrival at Saturn?", "options": ["1997", "2004", "2010", "2017"], '
    '"answer": "2004", "explanation": "It arrived in 2004."},'
    '{"question": "Mission end?", "options": ["2004", "2010", "2017", "2020"], '
    '"answer": "2017", "explanation": "The Grand Finale was in 2017."},'
    '{"question": "Launch vehicle?", "options": ["Titan IV", "Atlas V", "Delta II", "Saturn V"], '
    '"answer": "Titan IV", "explanation": "Cassini launched on a Titan IV."}'
    "]}"
)


def make_quiz_artifact(session: Session) -> int:
    """A ready quiz artifact with a real primary file on disk."""
    document = Document(
        workspace_id=1,
        title="Cassini Quiz",
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()

    artifact = Artifact(document_id=document.id, workspace_id=1, format="quiz")
    session.add(artifact)
    session.commit()

    built = quiz.build(_MODEL_REPLY, [])
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
    """A ready quiz artifact each test can drive over HTTP."""
    with create_session_factory(engine)() as session:
        return make_quiz_artifact(session)


async def test_a_fresh_quiz_starts_with_every_question_in_scope(
    client: AsyncClient, artifact_id: int
) -> None:
    """GET on a never-attempted quiz artifact must synthesize an empty,
    all-questions-in-scope state rather than erroring or returning null."""
    response = await client.get(f"/artifacts/{artifact_id}")

    assert response.status_code == 200
    state = response.json()["quiz_state"]
    assert state["generation"] == 1
    assert state["mode"] == "all"
    assert state["active_question_indices"] == [0, 1, 2]
    assert state["answers"] == {}


async def test_answering_persists_across_requests(
    client: AsyncClient, artifact_id: int
) -> None:
    """An answer written by PUT must be readable back on the next GET — the
    whole point of persisting it instead of keeping it in memory."""
    put = await client.put(
        f"/artifacts/{artifact_id}/quiz-state/answer",
        json={"question_index": 0, "selected_option_index": 1},
    )
    assert put.status_code == 200
    assert put.json()["answers"] == {"0": 1}

    get = await client.get(f"/artifacts/{artifact_id}")
    assert get.json()["quiz_state"]["answers"] == {"0": 1}


async def test_a_non_scoped_question_index_is_rejected(
    client: AsyncClient, artifact_id: int
) -> None:
    """The HTTP layer must surface the pure function's bounds check as a
    409, not a 500 or a silently-accepted write."""
    response = await client.put(
        f"/artifacts/{artifact_id}/quiz-state/answer",
        json={"question_index": 99, "selected_option_index": 0},
    )
    assert response.status_code == 409


async def test_retake_missed_after_completing_the_run(
    client: AsyncClient, artifact_id: int
) -> None:
    """The retake endpoint must read the quiz's real correct answers off
    disk to rescope the run to what was actually missed.

    Correct answers (by option index) are [1, 2, 0]; only question 1 is
    answered wrong here.
    """
    for index, choice in enumerate([1, 0, 0]):
        response = await client.put(
            f"/artifacts/{artifact_id}/quiz-state/answer",
            json={"question_index": index, "selected_option_index": choice},
        )
        assert response.status_code == 200

    retake = await client.put(
        f"/artifacts/{artifact_id}/quiz-state/retake", json={"mode": "missed"}
    )
    assert retake.status_code == 200
    body = retake.json()
    assert body["mode"] == "missed"
    assert body["active_question_indices"] == [1]


async def test_a_non_quiz_artifact_has_no_quiz_state(
    client: AsyncClient, engine: Engine, workspace: None
) -> None:
    """quiz_state must stay null for other formats, and mutating it must be
    refused rather than fabricating state for a non-quiz artifact."""
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
    assert response.json()["quiz_state"] is None

    rejected = await client.put(
        f"/artifacts/{summary_id}/quiz-state/answer",
        json={"question_index": 0, "selected_option_index": 0},
    )
    assert rejected.status_code == 409
