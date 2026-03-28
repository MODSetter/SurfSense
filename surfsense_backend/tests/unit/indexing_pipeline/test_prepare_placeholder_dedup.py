"""Unit tests for the duplicate-content safety logic in prepare_for_indexing.

Verifies that when an existing document's updated content matches another
document's content_hash, the system marks it as failed (for placeholders)
or leaves it untouched (for ready documents) — never deletes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import (
    compute_unique_identifier_hash,
)
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_connector_doc(**overrides) -> ConnectorDocument:
    defaults = {
        "title": "Test Doc",
        "source_markdown": "## Some new content",
        "unique_id": "file-001",
        "document_type": DocumentType.GOOGLE_DRIVE_FILE,
        "search_space_id": 1,
        "connector_id": 42,
        "created_by_id": "00000000-0000-0000-0000-000000000001",
    }
    defaults.update(overrides)
    return ConnectorDocument(**defaults)


def _make_existing_doc(connector_doc: ConnectorDocument, *, status: dict) -> MagicMock:
    """Build a MagicMock that looks like an ORM Document with given status."""
    doc = MagicMock(spec=Document)
    doc.id = 999
    doc.unique_identifier_hash = compute_unique_identifier_hash(connector_doc)
    doc.content_hash = "old-placeholder-content-hash"
    doc.title = connector_doc.title
    doc.status = status
    return doc


def _mock_session_for_dedup(existing_doc, *, has_duplicate: bool):
    """Build a session whose sequential execute() calls return:

    1. The *existing_doc* for the unique_identifier_hash lookup.
    2. A row (or None) for the duplicate content_hash check.
    """
    session = AsyncMock()

    existing_result = MagicMock()
    existing_result.scalars.return_value.first.return_value = existing_doc

    dup_result = MagicMock()
    dup_result.scalars.return_value.first.return_value = 42 if has_duplicate else None

    session.execute = AsyncMock(side_effect=[existing_result, dup_result])
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_pending_placeholder_with_duplicate_content_is_marked_failed():
    """A placeholder (pending) whose updated content duplicates another doc
    must be marked as FAILED — never deleted."""
    cdoc = _make_connector_doc(source_markdown="## Shared content")
    existing = _make_existing_doc(cdoc, status=DocumentStatus.pending())

    session = _mock_session_for_dedup(existing, has_duplicate=True)
    pipeline = IndexingPipelineService(session)

    results = await pipeline.prepare_for_indexing([cdoc])

    assert results == [], "duplicate should not be returned for indexing"

    assert DocumentStatus.is_state(existing.status, DocumentStatus.FAILED)
    assert "Duplicate content" in existing.status.get("reason", "")
    session.delete.assert_not_called()


async def test_ready_document_with_duplicate_content_is_left_untouched():
    """A READY document whose updated content duplicates another doc
    must be left completely untouched — not failed, not deleted."""
    cdoc = _make_connector_doc(source_markdown="## Shared content")
    existing = _make_existing_doc(cdoc, status=DocumentStatus.ready())

    session = _mock_session_for_dedup(existing, has_duplicate=True)
    pipeline = IndexingPipelineService(session)

    results = await pipeline.prepare_for_indexing([cdoc])

    assert results == [], "duplicate should not be returned for indexing"

    assert DocumentStatus.is_state(existing.status, DocumentStatus.READY)
    session.delete.assert_not_called()
