from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import Document, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def pipeline(mock_session):
    return IndexingPipelineService(mock_session)


def _make_execute_side_effect(doc_by_hash: dict):
    """Return a side_effect for session.execute that resolves documents by hash."""

    async def _side_effect(stmt):
        result = MagicMock()
        for h, doc in doc_by_hash.items():
            if h in str(stmt.compile(compile_kwargs={"literal_binds": True})):
                result.scalars.return_value.first.return_value = doc
                return result
        result.scalars.return_value.first.return_value = None
        return result

    return _side_effect


async def test_updates_hash_and_type_for_legacy_document(
    pipeline, mock_session, make_connector_document
):
    """Legacy Composio document gets unique_identifier_hash and document_type updated."""
    doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-abc",
        search_space_id=1,
    )

    legacy_hash = compute_identifier_hash("COMPOSIO_GMAIL_CONNECTOR", "msg-abc", 1)
    native_hash = compute_identifier_hash("GOOGLE_GMAIL_CONNECTOR", "msg-abc", 1)

    existing = MagicMock(spec=Document)
    existing.unique_identifier_hash = legacy_hash
    existing.document_type = DocumentType.COMPOSIO_GMAIL_CONNECTOR

    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = existing
    mock_session.execute = AsyncMock(return_value=result_mock)

    await pipeline.migrate_legacy_docs([doc])

    assert existing.unique_identifier_hash == native_hash
    assert existing.document_type == DocumentType.GOOGLE_GMAIL_CONNECTOR
    mock_session.commit.assert_awaited_once()


async def test_noop_when_no_legacy_document_exists(
    pipeline, mock_session, make_connector_document
):
    """No updates when no legacy Composio document is found in DB."""
    doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-xyz",
        search_space_id=1,
    )

    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)

    await pipeline.migrate_legacy_docs([doc])

    mock_session.commit.assert_awaited_once()


async def test_skips_non_google_doc_types(
    pipeline, mock_session, make_connector_document
):
    """Non-Google doc types have no legacy mapping and trigger no DB query."""
    doc = make_connector_document(
        document_type=DocumentType.SLACK_CONNECTOR,
        unique_id="slack-123",
        search_space_id=1,
    )

    await pipeline.migrate_legacy_docs([doc])

    mock_session.execute.assert_not_awaited()
    mock_session.commit.assert_awaited_once()


async def test_handles_all_three_google_types(
    pipeline, mock_session, make_connector_document
):
    """Each native Google type correctly maps to its Composio legacy type."""
    mappings = [
        (DocumentType.GOOGLE_GMAIL_CONNECTOR, "COMPOSIO_GMAIL_CONNECTOR"),
        (DocumentType.GOOGLE_CALENDAR_CONNECTOR, "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"),
        (DocumentType.GOOGLE_DRIVE_FILE, "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"),
    ]
    for native_type, expected_legacy in mappings:
        doc = make_connector_document(
            document_type=native_type,
            unique_id="id-1",
            search_space_id=1,
        )

        existing = MagicMock(spec=Document)
        existing.document_type = DocumentType(expected_legacy)

        result_mock = MagicMock()
        result_mock.scalars.return_value.first.return_value = existing
        mock_session.execute = AsyncMock(return_value=result_mock)
        mock_session.commit = AsyncMock()

        await pipeline.migrate_legacy_docs([doc])

        assert existing.document_type == native_type
