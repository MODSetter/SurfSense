from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import EmbeddingNotChosenError, active_index
from modules.embedding.bundled import BGE
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration

NOTE = """# Cassini

The orbiter reached Saturn in 2004.

It carried the Huygens probe, which landed on Titan.
"""


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def make_note(session: Session, content: str = NOTE) -> Document:
    """A workspace holding one pending note, as the API would have left it."""
    workspace = Workspace(name="Saturn")
    session.add(workspace)
    session.flush()

    note = Document(
        workspace_id=workspace.id,
        title="Cassini",
        document_type=DocumentType.NOTE,
        content=content,
    )
    session.add(note)
    session.commit()
    return note


def test_a_note_becomes_ready_and_searchable(
    session: Session, stub_model: None
) -> None:
    """Ready means both halves of hybrid search can reach the text."""
    note = make_note(session)

    run(note.id)

    session.expire_all()
    assert note.status is DocumentStatus.READY
    assert note.error_message is None
    assert note.content == NOTE

    chunk = session.scalars(text("SELECT id FROM chunks")).all()
    assert len(chunk) == 1

    keyword = session.scalar(
        text("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'Huygens'")
    )
    assert keyword == chunk[0]

    # The stub embeds each chunk from its content, so search for that vector.
    content = session.scalar(text("SELECT content FROM chunks"))
    width = BGE.dimension
    nearest = session.scalar(
        text(
            "SELECT rowid FROM chunk_vectors "
            "WHERE embedding MATCH :vector ORDER BY distance LIMIT 1"
        ),
        {"vector": _stub_vector(content, width)},
    )
    assert nearest == chunk[0]


def test_a_ready_note_records_the_index_it_was_embedded_into(
    session: Session, stub_model: None
) -> None:
    """What a later re-embed reads to know which documents it has reached."""
    note = make_note(session)

    run(note.id)

    session.expire_all()
    assert note.embedding_index_id == active_index(session).id


def test_ingest_before_an_embedder_is_chosen_fails_with_a_reason(
    unlocked_engine: Engine, stub_model: None
) -> None:
    """Onboarding gates the UI, not the API: a queued job must not guess a model."""
    with create_session_factory(unlocked_engine)() as session:
        note = make_note(session)

        with pytest.raises(EmbeddingNotChosenError):
            run(note.id)

        session.expire_all()
        assert note.status is DocumentStatus.FAILED
        assert "no embedding model" in (note.error_message or "")


def test_a_chunk_points_back_at_its_lines(session: Session, stub_model: None) -> None:
    """A citation has to name where in the document it came from."""
    note = make_note(session, "\n\n".join(f"Paragraph {n}." for n in range(200)))

    run(note.id)

    spans = session.execute(
        text("SELECT content, start_line, end_line FROM chunks ORDER BY position")
    ).all()
    assert len(spans) > 1

    markdown = note.content or ""
    for content, start, end in spans:
        # The recorded span marks the lines holding the chunk's first and last
        # characters, wherever the chunker chose to cut.
        offset = markdown.index(content)
        assert start == markdown.count("\n", 0, offset) + 1
        assert end == markdown.count("\n", 0, offset + len(content) - 1) + 1


def test_an_uploaded_file_is_read_from_disk(session: Session, stub_model: None) -> None:
    """A FILE carries no content until ingest puts the parsed text there."""
    workspace = Workspace(name="Saturn")
    session.add(workspace)
    session.flush()

    document = Document(
        workspace_id=workspace.id,
        title="notes.md",
        document_type=DocumentType.FILE,
        dedup_key="abc",
        document_metadata={"suffix": ".md"},
    )
    session.add(document)
    session.commit()

    folder = get_storage_settings().document_dir(workspace.id, document.id)
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text(NOTE, encoding="utf-8")

    run(document.id)

    session.expire_all()
    assert document.status is DocumentStatus.READY
    assert document.content == NOTE
    # The text lives in the row; a copy on disk would be a second truth.
    assert [path.name for path in folder.iterdir()] == ["notes.md"]


def test_a_second_run_replaces_the_first_ones_chunks(
    session: Session, stub_model: None
) -> None:
    """Editing a note reindexes it, and the old text stops being findable."""
    note = make_note(session)
    run(note.id)

    note.content = "# Cassini\n\nThe mission ended in 2017."
    session.commit()
    run(note.id)

    assert session.scalar(text("SELECT count(*) FROM chunks")) == 1
    assert session.scalar(text("SELECT count(*) FROM chunk_vectors")) == 1
    assert (
        session.scalar(
            text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Huygens'")
        )
        == 0
    )


def test_a_missing_file_leaves_a_reason(session: Session, stub_model: None) -> None:
    """The documents view shows why, and the retry route can be offered."""
    workspace = Workspace(name="Saturn")
    session.add(workspace)
    session.flush()
    document = Document(
        workspace_id=workspace.id,
        title="gone.pdf",
        document_type=DocumentType.FILE,
        document_metadata={"suffix": ".pdf"},
    )
    session.add(document)
    session.commit()

    with pytest.raises(FileNotFoundError):
        run(document.id)

    session.expire_all()
    assert document.status is DocumentStatus.FAILED
    assert "no longer on disk" in (document.error_message or "")


def test_an_embedding_failure_leaves_a_reason(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model files are missing or corrupt: fail the row, keep no chunks."""
    note = make_note(session)

    def boom(*_args: object) -> list[list[float]]:
        raise RuntimeError("the model could not be loaded")

    # Overrides the deterministic embed stub_model installed.
    monkeypatch.setattr("modules.embedding.encoder.embed", boom)

    with pytest.raises(RuntimeError, match="could not be loaded"):
        run(note.id)

    session.expire_all()
    assert note.status is DocumentStatus.FAILED
    assert note.error_message
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_a_document_deleted_before_ingest_is_not_an_error(
    engine: Engine, stub_model: None
) -> None:
    """The upload route commits before enqueueing, and a user can delete in between."""
    run(9999)


def test_a_cancelled_document_is_left_alone(session: Session, stub_model: None) -> None:
    """The API marks cancelled before the worker pops the job."""
    note = make_note(session)
    note.status = DocumentStatus.CANCELLED
    session.commit()

    run(note.id)

    session.expire_all()
    assert note.status is DocumentStatus.CANCELLED
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_ingest_stops_if_cancelled_while_parsing(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancel mid-job must not be overwritten with ready or failed."""
    note = make_note(session)

    def parse_and_cancel(document: Document) -> str:
        with create_session_factory(session.get_bind())() as other:
            row = other.get(Document, document.id)
            row.status = DocumentStatus.CANCELLED
            other.commit()
        return NOTE

    monkeypatch.setattr("worker.ingestion.parsing.markdown_for", parse_and_cancel)

    run(note.id)

    session.expire_all()
    assert note.status is DocumentStatus.CANCELLED
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_the_worker_opens_the_database_the_api_wrote(
    session: Session, stub_model: None, tmp_path: Path
) -> None:
    """Both processes read the same path out of settings, not from each other."""
    note = make_note(session)

    run(note.id)

    assert get_storage_settings().database_path == tmp_path / "surfsense.db"
    session.expire_all()
    assert note.status is DocumentStatus.READY


def test_the_bundled_encoder_embeds_a_note_offline(
    session: Session, real_model: Path
) -> None:
    """The real path: no stub, no network, a 384-wide vector per chunk."""
    note = make_note(session)

    run(note.id)

    session.expire_all()
    assert note.status is DocumentStatus.READY

    width = session.scalar(text("SELECT length(embedding) / 4 FROM chunks LIMIT 1"))
    assert width == BGE.dimension

    keyword = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Titan'")
    )
    assert keyword == 1


def _stub_vector(content: str, width: int) -> str:
    """The JSON the stub_model fixture produces for a chunk of this content."""
    import json

    return json.dumps([float(len(content) % 97)] * width)
