"""Hybrid retrieval over a real index: keyword, meaning, and the workspace edge."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from shared.search import retrieve
from worker.ingestion import run

pytestmark = pytest.mark.integration

# Five distinct topics, so ranking has to discriminate, not just return the one
# thing present. No word of the cat line recurs in the paraphrase query below.
DOCS = {
    "cat": "The feline dozed on the warm windowsill.",
    "finance": "Quarterly revenue climbed after the spring product launch.",
    "mountains": "The hikers reached the summit before the storm rolled in.",
    "code": "She debugged the null pointer exception in the payment module.",
    "cooking": "The recipe calls for two cups of flour and a pinch of salt.",
}


def _ingest(session: Session, workspace_id: int, content: str) -> int:
    """Leave a note the way the API would, then run it to ready."""
    note = Document(
        workspace_id=workspace_id,
        title="note",
        document_type=DocumentType.NOTE,
        content=content,
    )
    session.add(note)
    session.commit()
    run(note.id)
    return note.id


@pytest.fixture
def library(engine: Engine, real_model: object) -> Iterator[tuple[Session, int, dict]]:
    """One workspace holding the whole corpus, each note indexed for real."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Notes")
        session.add(workspace)
        session.flush()
        ids = {
            topic: _ingest(session, workspace.id, content)
            for topic, content in DOCS.items()
        }
        yield session, workspace.id, ids


def test_a_keyword_query_finds_its_document(
    library: tuple[Session, int, dict],
) -> None:
    """The lexical leg ranks the one note that shares the word first."""
    session, workspace_id, ids = library

    hits = retrieve(session, workspace_id, "revenue")

    assert hits[0].document_id == ids["finance"]


def test_a_paraphrase_finds_its_document_through_meaning(
    library: tuple[Session, int, dict],
) -> None:
    """No shared word with the cat note, so only the vector leg can reach it."""
    session, workspace_id, ids = library

    hits = retrieve(session, workspace_id, "a cat napping in sunlight")

    # Every content word is absent from the corpus, so the keyword leg is empty
    # and only meaning can have found it.
    assert hits[0].document_id == ids["cat"]


def test_a_hit_carries_its_document_and_lines(
    library: tuple[Session, int, dict],
) -> None:
    """A citation needs the document and the span it came from."""
    session, workspace_id, ids = library

    hit = retrieve(session, workspace_id, "revenue")[0]

    assert hit.document_id == ids["finance"]
    assert hit.content
    assert hit.start_line is not None
    assert hit.end_line is not None


def test_retrieval_stays_within_the_workspace(
    engine: Engine, real_model: object
) -> None:
    """The other workspace's note is the closest match, and still never returned."""
    with create_session_factory(engine)() as session:
        mine = Workspace(name="Mine")
        other = Workspace(name="Other")
        session.add_all([mine, other])
        session.flush()
        _ingest(session, mine.id, DOCS["cat"])
        theirs = _ingest(session, other.id, DOCS["finance"])

        hits = retrieve(session, mine.id, "revenue")

        assert all(hit.document_id != theirs for hit in hits)


def test_an_empty_workspace_returns_nothing(
    engine: Engine, real_model: object
) -> None:
    """A workspace with no documents ranks nothing, and does not error."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Empty")
        session.add(workspace)
        session.commit()

        assert retrieve(session, workspace.id, "anything") == []


def test_an_empty_query_returns_nothing(engine: Engine) -> None:
    """Short-circuits before the model, so it needs none on disk."""
    with create_session_factory(engine)() as session:
        assert retrieve(session, 1, "   ") == []
