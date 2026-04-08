"""Integration tests: ConnectorService search transparently includes legacy Composio docs.

These tests exercise ``ConnectorService.search_google_drive`` and
``ConnectorService.search_files`` through a real PostgreSQL database.
They verify that the legacy-type alias expansion works end-to-end:
searching for native Google Drive docs also returns old Composio-typed docs.
"""

from __future__ import annotations

import pytest

from app.services.connector_service import ConnectorService

pytestmark = pytest.mark.integration


async def test_search_google_drive_includes_legacy_composio_docs(
    async_engine, committed_google_data, patched_session_factory, patched_embed
):
    """search_google_drive returns both GOOGLE_DRIVE_FILE and COMPOSIO_GOOGLE_DRIVE_CONNECTOR docs."""
    space_id = committed_google_data["search_space_id"]

    async with patched_session_factory() as session:
        service = ConnectorService(session, search_space_id=space_id)
        _, raw_docs = await service.search_google_drive(
            user_query="quarterly budget",
            search_space_id=space_id,
            top_k=10,
        )

    returned_types = set()
    for doc in raw_docs:
        doc_info = doc.get("document", {})
        dtype = doc_info.get("document_type")
        if dtype:
            returned_types.add(dtype)

    assert "GOOGLE_DRIVE_FILE" in returned_types, (
        "Native Drive docs should appear in search_google_drive results"
    )
    assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" in returned_types, (
        "Legacy Composio Drive docs should appear in search_google_drive results"
    )
    assert "FILE" not in returned_types, (
        "Plain FILE docs should NOT appear in search_google_drive results"
    )


async def test_search_files_does_not_include_google_types(
    async_engine, committed_google_data, patched_session_factory, patched_embed
):
    """search_files returns only FILE docs, not Google Drive docs."""
    space_id = committed_google_data["search_space_id"]

    async with patched_session_factory() as session:
        service = ConnectorService(session, search_space_id=space_id)
        _, raw_docs = await service.search_files(
            user_query="quarterly budget",
            search_space_id=space_id,
            top_k=10,
        )

    returned_types = set()
    for doc in raw_docs:
        doc_info = doc.get("document", {})
        dtype = doc_info.get("document_type")
        if dtype:
            returned_types.add(dtype)

    if returned_types:
        assert "GOOGLE_DRIVE_FILE" not in returned_types
        assert "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" not in returned_types
