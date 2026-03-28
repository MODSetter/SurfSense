"""Integration tests for IndexingPipelineService.index_batch()."""

import pytest
from sqlalchemy import select

from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_index_batch_creates_ready_documents(
    db_session, db_search_space, make_connector_document, mocker
):
    """index_batch prepares and indexes a batch, resulting in READY documents."""
    space_id = db_search_space.id
    docs = [
        make_connector_document(
            document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
            unique_id="msg-batch-1",
            search_space_id=space_id,
            source_markdown="## Email 1\n\nBody",
        ),
        make_connector_document(
            document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
            unique_id="msg-batch-2",
            search_space_id=space_id,
            source_markdown="## Email 2\n\nDifferent body",
        ),
    ]

    service = IndexingPipelineService(session=db_session)
    results = await service.index_batch(docs, llm=mocker.Mock())

    assert len(results) == 2

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == space_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 2

    for row in rows:
        assert DocumentStatus.is_state(row.status, DocumentStatus.READY)
        assert row.content is not None
        assert row.embedding is not None


@pytest.mark.usefixtures("patched_summarize", "patched_embed_texts", "patched_chunk_text")
async def test_index_batch_empty_returns_empty(db_session, mocker):
    """index_batch with empty input returns an empty list."""
    service = IndexingPipelineService(session=db_session)
    results = await service.index_batch([], llm=mocker.Mock())
    assert results == []
