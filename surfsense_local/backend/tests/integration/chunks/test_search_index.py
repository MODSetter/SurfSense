"""The two index tables no foreign key reaches, and the triggers that do."""

import struct

import pytest
from sqlalchemy import Engine, insert, text
from sqlalchemy.exc import OperationalError

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace
from shared.config import get_search_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def chunked(engine: Engine) -> Engine:
    """A workspace holding one document of one indexed chunk."""
    width = get_search_settings().embedding_dimension

    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="Research"))
        connection.execute(
            insert(Document).values(
                id=1,
                workspace_id=1,
                title="report.pdf",
                document_type=DocumentType.FILE,
            )
        )
        connection.execute(
            insert(Chunk).values(
                id=1, document_id=1, position=0, content="the ship sails at dawn"
            )
        )
        connection.execute(
            text("INSERT INTO chunk_vectors(rowid, embedding) VALUES (1, :embedding)"),
            {"embedding": struct.pack(f"{width}f", *([0.1] * width))},
        )
    return engine


def _rows(engine: Engine, table: str) -> list[int]:
    with engine.connect() as connection:
        return [
            row[0] for row in connection.execute(text(f"SELECT rowid FROM {table}"))
        ]


def test_a_new_chunk_is_searchable(chunked: Engine) -> None:
    """Ingest writes only to chunks; the keyword index has to follow on its own."""
    with chunked.connect() as connection:
        hits = connection.execute(
            text("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'ship'")
        ).all()

    assert [row[0] for row in hits] == [1]


def test_an_edited_chunk_stops_matching_its_old_text(chunked: Engine) -> None:
    """An external-content index keeps no copy, so a stale entry matches forever."""
    with chunked.begin() as connection:
        connection.execute(
            text("UPDATE chunks SET content = 'the train departs' WHERE id = 1")
        )

    with chunked.connect() as connection:
        assert (
            connection.execute(
                text("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'ship'")
            ).all()
            == []
        )
        assert (
            connection.execute(
                text("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'train'")
            ).scalar()
            == 1
        )


def test_deleting_a_document_empties_both_indexes(chunked: Engine) -> None:
    """The delete arrives at chunks as a cascade, which still has to fire the triggers.

    Nothing else clears these two: they are virtual tables, so no foreign key
    reaches them and search would keep answering for a deleted document.
    """
    with chunked.begin() as connection:
        connection.execute(text("DELETE FROM documents WHERE id = 1"))

    assert _rows(chunked, "chunks") == []
    assert _rows(chunked, "chunks_fts") == []
    assert _rows(chunked, "chunk_vectors") == []


def test_a_vector_of_the_wrong_width_is_refused(chunked: Engine) -> None:
    """A vector from another model is not the wrong shape, it is unrelated numbers.

    Stored anyway, it would rank against real ones and quietly poison search.
    """
    with (
        pytest.raises(OperationalError, match="Dimension mismatch"),
        chunked.begin() as connection,
    ):
        connection.execute(
            text("INSERT INTO chunk_vectors(rowid, embedding) VALUES (2, :e)"),
            {"e": struct.pack("3f", 0.1, 0.2, 0.3)},
        )
