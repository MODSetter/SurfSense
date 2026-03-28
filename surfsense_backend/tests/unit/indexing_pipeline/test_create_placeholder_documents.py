"""Unit tests for IndexingPipelineService.create_placeholder_documents."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import DocumentStatus, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_placeholder(**overrides) -> PlaceholderInfo:
    defaults = {
        "title": "Test Doc",
        "document_type": DocumentType.GOOGLE_DRIVE_FILE,
        "unique_id": "file-001",
        "search_space_id": 1,
        "connector_id": 42,
        "created_by_id": "00000000-0000-0000-0000-000000000001",
    }
    defaults.update(overrides)
    return PlaceholderInfo(**defaults)


def _uid_hash(p: PlaceholderInfo) -> str:
    return compute_identifier_hash(
        p.document_type.value, p.unique_id, p.search_space_id
    )


def _session_with_existing_hashes(existing: set[str] | None = None):
    """Build an AsyncMock session whose batch-query returns *existing* hashes."""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(existing or [])
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_empty_input_returns_zero_without_db_calls():
    session = AsyncMock()
    pipeline = IndexingPipelineService(session)

    result = await pipeline.create_placeholder_documents([])

    assert result == 0
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_creates_documents_with_pending_status_and_commits():
    session = _session_with_existing_hashes(set())
    pipeline = IndexingPipelineService(session)
    p = _make_placeholder(title="My File", unique_id="file-abc")

    result = await pipeline.create_placeholder_documents([p])

    assert result == 1
    session.add.assert_called_once()

    doc = session.add.call_args[0][0]
    assert doc.title == "My File"
    assert doc.document_type == DocumentType.GOOGLE_DRIVE_FILE
    assert doc.content == "Pending..."
    assert DocumentStatus.is_state(doc.status, DocumentStatus.PENDING)
    assert doc.search_space_id == 1
    assert doc.connector_id == 42

    session.commit.assert_awaited_once()


async def test_existing_documents_are_skipped():
    """Placeholders whose unique_identifier_hash already exists are not re-created."""
    existing_p = _make_placeholder(unique_id="already-there")
    new_p = _make_placeholder(unique_id="brand-new")

    existing_hash = _uid_hash(existing_p)
    session = _session_with_existing_hashes({existing_hash})
    pipeline = IndexingPipelineService(session)

    result = await pipeline.create_placeholder_documents([existing_p, new_p])

    assert result == 1
    doc = session.add.call_args[0][0]
    assert doc.unique_identifier_hash == _uid_hash(new_p)


async def test_duplicate_unique_ids_within_input_are_deduped():
    """Same unique_id passed twice only produces one placeholder."""
    p1 = _make_placeholder(unique_id="dup-id", title="First")
    p2 = _make_placeholder(unique_id="dup-id", title="Second")

    session = _session_with_existing_hashes(set())
    pipeline = IndexingPipelineService(session)

    result = await pipeline.create_placeholder_documents([p1, p2])

    assert result == 1
    session.add.assert_called_once()


async def test_integrity_error_on_commit_returns_zero():
    """IntegrityError during commit (race condition) is swallowed gracefully."""
    session = _session_with_existing_hashes(set())
    session.commit = AsyncMock(side_effect=IntegrityError("dup", {}, None))
    pipeline = IndexingPipelineService(session)
    p = _make_placeholder()

    result = await pipeline.create_placeholder_documents([p])

    assert result == 0
    session.rollback.assert_awaited_once()
