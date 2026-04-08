from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import Document, DocumentType
from app.indexing_pipeline.document_hashing import compute_unique_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def pipeline(mock_session):
    return IndexingPipelineService(mock_session)


async def test_calls_prepare_then_index_per_document(pipeline, make_connector_document):
    """index_batch calls prepare_for_indexing, then index() for each returned doc."""
    doc1 = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-1",
        search_space_id=1,
    )
    doc2 = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-2",
        search_space_id=1,
    )

    orm1 = MagicMock(spec=Document)
    orm1.unique_identifier_hash = compute_unique_identifier_hash(doc1)
    orm2 = MagicMock(spec=Document)
    orm2.unique_identifier_hash = compute_unique_identifier_hash(doc2)

    mock_llm = MagicMock()

    pipeline.prepare_for_indexing = AsyncMock(return_value=[orm1, orm2])
    pipeline.index = AsyncMock(side_effect=lambda doc, cdoc, llm: doc)

    results = await pipeline.index_batch([doc1, doc2], mock_llm)

    pipeline.prepare_for_indexing.assert_awaited_once_with([doc1, doc2])
    assert pipeline.index.await_count == 2
    assert results == [orm1, orm2]


async def test_empty_input_returns_empty(pipeline):
    """Empty connector_docs list returns empty result."""
    pipeline.prepare_for_indexing = AsyncMock(return_value=[])

    results = await pipeline.index_batch([], MagicMock())

    assert results == []


async def test_skips_document_without_matching_connector_doc(
    pipeline, make_connector_document
):
    """If prepare returns a doc whose hash has no matching ConnectorDocument, it's skipped."""
    doc1 = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-1",
        search_space_id=1,
    )

    orphan_orm = MagicMock(spec=Document)
    orphan_orm.unique_identifier_hash = "nonexistent-hash"

    pipeline.prepare_for_indexing = AsyncMock(return_value=[orphan_orm])
    pipeline.index = AsyncMock()

    results = await pipeline.index_batch([doc1], MagicMock())

    pipeline.index.assert_not_awaited()
    assert results == []
