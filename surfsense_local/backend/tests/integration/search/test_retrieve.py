"""Hybrid retrieval over a real index: keyword, meaning, and the workspace edge."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from shared.search import CANDIDATES, retrieve
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

    # Not a quiet keyword leg: "a" and "in" match the cooking note, which ranks
    # first on BM25. A match covering one term of five has to stay weak enough
    # for meaning to win, or every question carries its stopwords' documents.
    assert hits[0].document_id == ids["cat"]


def test_a_hit_carries_its_document_and_lines(
    library: tuple[Session, int, dict],
) -> None:
    """A citation needs the document and the span it came from."""
    session, workspace_id, ids = library

    hit = retrieve(session, workspace_id, "revenue")[0]

    assert hit.document_id == ids["finance"]
    assert hit.title == "note"
    assert hit.content
    assert hit.start_line is not None
    assert hit.end_line is not None


def test_retrieval_stays_within_selected_documents(
    library: tuple[Session, int, dict],
) -> None:
    """An explicit source selection excludes every other document."""
    session, workspace_id, ids = library

    hits = retrieve(
        session,
        workspace_id,
        "revenue",
        document_ids=[ids["cat"]],
    )

    assert hits
    assert {hit.document_id for hit in hits} == {ids["cat"]}


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


def test_a_hindi_question_finds_the_note_that_answers_it(
    engine: Engine, real_model: object
) -> None:
    """One word apart, so only the keyword leg can choose between them.

    bge-small is English-only and these three lines differ by a single noun, so
    meaning leaves them near-tied and term coverage has to break it. Cut at its
    virama `स्कैनर` is `स` + `नर`, which the index does not hold, and the leg
    that should decide abstains.
    """
    notes = {
        "scanner": "स्कैनर की बैटरी आठ घंटे चलती है।",
        "printer": "प्रिंटर की बैटरी आठ घंटे चलती है।",
        "camera": "कैमरा की बैटरी आठ घंटे चलती है।",
    }
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="नोट्स")
        session.add(workspace)
        session.flush()
        ids = {
            topic: _ingest(session, workspace.id, content)
            for topic, content in notes.items()
        }

        hits = retrieve(session, workspace.id, "स्कैनर की बैटरी कितने घंटे चलती है?")

        assert hits[0].document_id == ids["scanner"]


def test_a_crowded_neighbour_workspace_does_not_reorder_mine(
    engine: Engine, real_model: object
) -> None:
    """Another workspace's documents must not decide what mine ranks first.

    KNN takes the global nearest `CANDIDATES` before the workspace filter runs,
    so a neighbour holding that many closer chunks leaves my own notes out of
    the semantic leg. Scored as cosine zero rather than unmeasured, the note
    that merely carries more of the query's words wins.
    """
    query = "a cat napping in sunlight"
    with create_session_factory(engine)() as session:
        mine = Workspace(name="Mine")
        neighbour = Workspace(name="Neighbour")
        session.add_all([mine, neighbour])
        session.flush()
        # Closer to the query than anything of mine can be, and enough of them
        # to leave no room.
        for _ in range(CANDIDATES):
            _ingest(session, neighbour.id, query)
        # Two words of the query against three, so coverage alone prefers the
        # invoice; meaning is the only thing that puts the dozing cat first.
        dozing = _ingest(session, mine.id, "The feline dozed in the warm sunlight.")
        _ingest(
            session, mine.id, "Invoice: a crate of tinned cat food shipped in bulk."
        )

        hits = retrieve(session, mine.id, query)

        assert hits[0].document_id == dozing


def test_an_empty_workspace_returns_nothing(engine: Engine, real_model: object) -> None:
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


def test_an_empty_document_selection_returns_nothing(engine: Engine) -> None:
    """An explicit empty selection short-circuits before loading the model."""
    with create_session_factory(engine)() as session:
        assert retrieve(session, 1, "anything", document_ids=[]) == []
