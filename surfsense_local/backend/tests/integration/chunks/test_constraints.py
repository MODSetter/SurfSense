"""Chunks: derived rows that must not outlive or duplicate their document."""

import pytest
from sqlalchemy import Engine, delete, exc, func, insert, select

from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace

pytestmark = pytest.mark.integration


def test_deleting_a_document_takes_its_chunks(engine: Engine) -> None:
    """Chunks are derived data; leaving them behind would poison later searches."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        connection.execute(
            insert(Document).values(
                id=1, workspace_id=1, title="x", document_type=DocumentType.FILE
            )
        )
        connection.execute(
            insert(Chunk).values(document_id=1, position=0, content="hello")
        )
        connection.execute(delete(Document).where(Document.id == 1))

        assert connection.execute(select(func.count()).select_from(Chunk)).scalar() == 0


def test_chunk_positions_are_unique_per_document(engine: Engine) -> None:
    """A retried ingest must not silently double every chunk of a document."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        connection.execute(
            insert(Document).values(
                id=1, workspace_id=1, title="x", document_type=DocumentType.FILE
            )
        )
        connection.execute(
            insert(Chunk).values(document_id=1, position=0, content="first")
        )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Chunk).values(document_id=1, position=0, content="again")
        )
