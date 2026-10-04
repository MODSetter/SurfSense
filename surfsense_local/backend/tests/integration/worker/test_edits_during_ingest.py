"""An edit the API commits while a document ingests survives the ingest.

`PATCH` has no processing guard, and right after an upload, while its parse
runs, is when people rename. Ingest must finish with what it produced, not
write back the row it read when it began.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration

OLD = "# Cassini\n\nIt carried the Huygens probe, which landed on Titan.\n"
NEW = "# Cassini\n\nThe mission ended in a dive into Saturn in 2017.\n"


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def workspace(session: Session) -> Workspace:
    """The workspace each document here belongs to."""
    saturn = Workspace(name="Saturn")
    session.add(saturn)
    session.flush()
    return saturn


def edit_while_parsing(
    session: Session, monkeypatch: pytest.MonkeyPatch, parsed: str, **changes: object
) -> None:
    """Commit `changes` to the row from another session, as the API would, while
    the worker's first parse runs; every parse returns what the row held then."""
    edited = False

    def parse_during_edit(document: Document) -> str:
        nonlocal edited
        if edited:
            return document.content or parsed
        edited = True
        with create_session_factory(session.get_bind())() as api:
            row = api.get(Document, document.id)
            for column, value in changes.items():
                setattr(row, column, value)
            api.commit()
        return parsed

    monkeypatch.setattr("worker.ingestion.parsing.markdown_for", parse_during_edit)


def test_a_file_renamed_during_its_parse_keeps_its_new_name(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without this the upload's name came back when ingest finished."""
    document = Document(
        workspace_id=workspace(session).id,
        title="scan-0042.md",
        document_type=DocumentType.FILE,
        dedup_key="abc",
        document_metadata={"suffix": ".md"},
    )
    session.add(document)
    session.commit()
    edit_while_parsing(session, monkeypatch, OLD, title="Cassini notes")

    run(document.id)

    session.expire_all()
    assert document.title == "Cassini notes"
    assert document.status is DocumentStatus.READY
    assert document.content == OLD


def test_a_note_edited_during_its_ingest_ends_with_the_new_text_indexed(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The edit queues another ingest; it must find the new text, not the old."""
    note = Document(
        workspace_id=workspace(session).id,
        title="Cassini",
        document_type=DocumentType.NOTE,
        content=OLD,
    )
    session.add(note)
    session.commit()
    edit_while_parsing(
        session, monkeypatch, OLD, content=NEW, status=DocumentStatus.PENDING
    )

    run(note.id)
    run(note.id)  # the ingest the edit enqueued

    session.expire_all()
    assert note.content == NEW
    assert note.status is DocumentStatus.READY

    def indexed(word: str) -> int:
        return session.scalar(
            text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH :word"),
            {"word": word},
        )

    assert (indexed("Huygens"), indexed("dive")) == (0, 1)
