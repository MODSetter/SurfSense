from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.document_persistence import persist_scratch_index

pytestmark = pytest.mark.unit


def _make_document(doc_id: int = 1) -> Document:
    document = MagicMock(spec=Document)
    document.id = doc_id
    document.content = None
    document.status = DocumentStatus.processing()
    return document


@pytest.mark.asyncio
async def test_persist_scratch_index_batches_commits(monkeypatch):
    monkeypatch.setattr(
        "app.indexing_pipeline.document_persistence.set_committed_value",
        lambda *_args, **_kwargs: None,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    document = _make_document()
    chunks = [Chunk(content=f"c{i}", embedding=[0.1], position=i) for i in range(5)]
    perf = MagicMock()

    await persist_scratch_index(
        session,
        document,
        "body",
        chunks,
        batch_size=2,
        perf=perf,
    )

    assert session.commit.await_count == 5
    assert document.status == DocumentStatus.ready()


@pytest.mark.asyncio
async def test_persist_scratch_index_empty_chunks(monkeypatch):
    monkeypatch.setattr(
        "app.indexing_pipeline.document_persistence.set_committed_value",
        lambda *_args, **_kwargs: None,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    document = _make_document()
    perf = MagicMock()

    await persist_scratch_index(
        session,
        document,
        "body",
        [],
        batch_size=200,
        perf=perf,
    )

    assert session.commit.await_count == 2
    assert document.status == DocumentStatus.ready()
