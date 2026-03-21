"""Integration tests: hybrid search correctly filters by document type lists.

These tests exercise the public ``hybrid_search`` method on
``ChucksHybridSearchRetriever`` with a real PostgreSQL database.
They verify that the ``.in_()`` SQL path works for list-of-types filtering,
which is the foundation of the Google unification changes.
"""

import pytest

from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever

from .conftest import DUMMY_EMBEDDING

pytestmark = pytest.mark.integration


async def test_list_of_types_returns_both_matching_doc_types(
    db_session, seed_google_docs
):
    """Searching with a list of document types returns documents of ALL listed types."""
    space_id = seed_google_docs["search_space"].id

    retriever = ChucksHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly report",
        top_k=10,
        search_space_id=space_id,
        document_type=["GOOGLE_DRIVE_FILE", "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"],
        query_embedding=DUMMY_EMBEDDING,
    )

    returned_types = {
        r["document"]["document_type"] for r in results if r.get("document")
    }
    assert "GOOGLE_DRIVE_FILE" in returned_types
    assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" in returned_types
    assert "FILE" not in returned_types


async def test_single_string_type_returns_only_that_type(db_session, seed_google_docs):
    """Searching with a single string type returns only documents of that exact type."""
    space_id = seed_google_docs["search_space"].id

    retriever = ChucksHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly report",
        top_k=10,
        search_space_id=space_id,
        document_type="GOOGLE_DRIVE_FILE",
        query_embedding=DUMMY_EMBEDDING,
    )

    returned_types = {
        r["document"]["document_type"] for r in results if r.get("document")
    }
    assert returned_types == {"GOOGLE_DRIVE_FILE"}


async def test_all_invalid_types_returns_empty(db_session, seed_google_docs):
    """Searching with a list of nonexistent types returns an empty list, no exceptions."""
    space_id = seed_google_docs["search_space"].id

    retriever = ChucksHybridSearchRetriever(db_session)
    results = await retriever.hybrid_search(
        query_text="quarterly report",
        top_k=10,
        search_space_id=space_id,
        document_type=["NONEXISTENT_TYPE"],
        query_embedding=DUMMY_EMBEDDING,
    )

    assert results == []
