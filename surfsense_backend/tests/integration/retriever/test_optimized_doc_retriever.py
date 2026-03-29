"""Integration tests for optimized DocumentHybridSearchRetriever.

Verifies the SQL ROW_NUMBER per-doc chunk limit and column pruning.
"""

import pytest

from app.retriever.documents_hybrid_search import (
    _MAX_FETCH_CHUNKS_PER_DOC,
    DocumentHybridSearchRetriever,
)

from .conftest import DUMMY_EMBEDDING

pytestmark = pytest.mark.integration


async def test_per_doc_chunk_limit_respected(db_session, seed_large_doc):
    """A document with 35 chunks should have at most _MAX_FETCH_CHUNKS_PER_DOC chunks returned."""
    space_id = seed_large_doc["search_space"].id

    retriever = DocumentHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly performance review",
        top_k=10,
        search_space_id=space_id,
        query_embedding=DUMMY_EMBEDDING,
    )

    large_doc_id = seed_large_doc["large_doc"].id
    for result in results:
        if result["document"].get("id") == large_doc_id:
            assert len(result["chunks"]) <= _MAX_FETCH_CHUNKS_PER_DOC
            assert len(result["chunks"]) == _MAX_FETCH_CHUNKS_PER_DOC
            break
    else:
        pytest.fail("Large doc not found in search results")


async def test_doc_metadata_populated(db_session, seed_large_doc):
    """Document metadata should be present from the RRF results."""
    space_id = seed_large_doc["search_space"].id

    retriever = DocumentHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly performance review",
        top_k=10,
        search_space_id=space_id,
        query_embedding=DUMMY_EMBEDDING,
    )

    assert len(results) >= 1
    for result in results:
        doc = result["document"]
        assert "id" in doc
        assert "title" in doc
        assert doc["title"]
        assert "document_type" in doc
        assert doc["document_type"] is not None


async def test_chunks_ordered_by_id(db_session, seed_large_doc):
    """Chunks within each document should be ordered by chunk ID."""
    space_id = seed_large_doc["search_space"].id

    retriever = DocumentHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly performance review",
        top_k=10,
        search_space_id=space_id,
        query_embedding=DUMMY_EMBEDDING,
    )

    for result in results:
        chunk_ids = [c["chunk_id"] for c in result["chunks"]]
        assert chunk_ids == sorted(chunk_ids), "Chunks not ordered by ID"
