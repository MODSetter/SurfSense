"""Integration test: _browse_recent_documents returns docs of multiple types.

Exercises the browse path (degenerate-query fallback) with a real PostgreSQL
database.  Verifies that passing a list of document types correctly returns
documents of all listed types -- the same ``.in_()`` SQL path used by hybrid
search but through the browse/recency-ordered code path.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_browse_recent_documents_with_list_type_returns_both(
    committed_google_data, patched_shielded_session
):
    """_browse_recent_documents returns docs of all types when given a list."""
    from app.agents.new_chat.tools.knowledge_base import _browse_recent_documents

    space_id = committed_google_data["search_space_id"]

    results = await _browse_recent_documents(
        search_space_id=space_id,
        document_type=["GOOGLE_DRIVE_FILE", "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"],
        top_k=10,
        start_date=None,
        end_date=None,
    )

    returned_types = set()
    for doc in results:
        doc_info = doc.get("document", {})
        dtype = doc_info.get("document_type")
        if dtype:
            returned_types.add(dtype)

    assert "GOOGLE_DRIVE_FILE" in returned_types, (
        "Native Drive docs should appear in browse results"
    )
    assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" in returned_types, (
        "Legacy Composio Drive docs should appear in browse results"
    )
