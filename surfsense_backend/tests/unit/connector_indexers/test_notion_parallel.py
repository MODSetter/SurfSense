"""Tests for Notion indexer migrated to the unified parallel pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.connector_indexers.notion_indexer as _mod
from app.db import DocumentType
from app.tasks.connector_indexers.notion_indexer import (
    _build_connector_doc,
    index_notion_pages,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_page(page_id: str = "page-1", title: str = "Test Page", content=None):
    if content is None:
        content = [{"type": "paragraph", "content": "Hello world", "children": []}]
    return {"page_id": page_id, "title": title, "content": content}


# ---------------------------------------------------------------------------
# Slice 1: _build_connector_doc tracer bullet
# ---------------------------------------------------------------------------


async def test_build_connector_doc_produces_correct_fields():
    """Tracer bullet: a single Notion page produces a ConnectorDocument with correct fields."""

    page = _make_page(page_id="abc-123", title="My Notion Page")
    markdown = "# My Notion Page\n\nHello world"

    doc = _build_connector_doc(
        page,
        markdown,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert doc.title == "My Notion Page"
    assert doc.unique_id == "abc-123"
    assert doc.document_type == DocumentType.NOTION_CONNECTOR
    assert doc.source_markdown == markdown
    assert doc.search_space_id == _SEARCH_SPACE_ID
    assert doc.connector_id == _CONNECTOR_ID
    assert doc.created_by_id == _USER_ID
    assert doc.should_summarize is True
    assert doc.metadata["page_title"] == "My Notion Page"
    assert doc.metadata["page_id"] == "abc-123"
    assert doc.metadata["connector_id"] == _CONNECTOR_ID
    assert doc.metadata["document_type"] == "Notion Page"
    assert doc.metadata["connector_type"] == "Notion"
    assert doc.fallback_summary is not None
    assert "My Notion Page" in doc.fallback_summary
    assert markdown in doc.fallback_summary


async def test_build_connector_doc_summary_disabled():
    """When enable_summary is False, should_summarize is False."""
    doc = _build_connector_doc(
        _make_page(),
        "# content",
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=False,
    )

    assert doc.should_summarize is False


# ---------------------------------------------------------------------------
# Shared fixtures for Slices 2-7 (full index_notion_pages tests)
# ---------------------------------------------------------------------------


def _mock_connector(enable_summary: bool = True):
    c = MagicMock()
    c.config = {"access_token": "tok"}
    c.enable_summary = enable_summary
    c.last_indexed_at = None
    return c


def _mock_notion_client(pages=None, skipped_count=0, legacy_token=False):
    client = MagicMock()
    client.get_all_pages = AsyncMock(return_value=pages if pages is not None else [])
    client.get_skipped_content_count = MagicMock(return_value=skipped_count)
    client.is_using_legacy_token = MagicMock(return_value=legacy_token)
    client.close = AsyncMock()
    client.set_retry_callback = MagicMock()
    return client


@pytest.fixture
def notion_mocks(monkeypatch):
    """Wire up all external boundary mocks for index_notion_pages."""
    mock_session = AsyncMock()
    mock_session.no_autoflush = MagicMock()

    mock_connector = _mock_connector()
    monkeypatch.setattr(
        _mod, "get_connector_by_id", AsyncMock(return_value=mock_connector),
    )

    notion_client = _mock_notion_client(pages=[_make_page()])
    monkeypatch.setattr(
        _mod, "NotionHistoryConnector", MagicMock(return_value=notion_client),
    )

    monkeypatch.setattr(
        _mod, "check_duplicate_document_by_hash", AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        _mod, "update_connector_last_indexed", AsyncMock(),
    )

    monkeypatch.setattr(
        _mod, "calculate_date_range", MagicMock(return_value=("2025-01-01", "2025-12-31")),
    )

    monkeypatch.setattr(
        _mod, "process_blocks", MagicMock(return_value="Converted markdown content"),
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
    mock_task_logger.log_task_progress = AsyncMock()
    mock_task_logger.log_task_success = AsyncMock()
    mock_task_logger.log_task_failure = AsyncMock()
    monkeypatch.setattr(
        _mod, "TaskLoggingService", MagicMock(return_value=mock_task_logger),
    )

    batch_mock = AsyncMock(return_value=([], 1, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.migrate_legacy_docs = AsyncMock()
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock),
    )

    return {
        "session": mock_session,
        "connector": mock_connector,
        "notion_client": notion_client,
        "task_logger": mock_task_logger,
        "pipeline_mock": pipeline_mock,
        "batch_mock": batch_mock,
    }


async def _run_index(mocks, **overrides):
    return await index_notion_pages(
        session=mocks["session"],
        connector_id=overrides.get("connector_id", _CONNECTOR_ID),
        search_space_id=overrides.get("search_space_id", _SEARCH_SPACE_ID),
        user_id=overrides.get("user_id", _USER_ID),
        start_date=overrides.get("start_date", "2025-01-01"),
        end_date=overrides.get("end_date", "2025-12-31"),
        update_last_indexed=overrides.get("update_last_indexed", True),
        on_retry_callback=overrides.get("on_retry_callback"),
        on_heartbeat_callback=overrides.get("on_heartbeat_callback"),
    )


# ---------------------------------------------------------------------------
# Slice 2: Full pipeline wiring
# ---------------------------------------------------------------------------


async def test_one_page_calls_pipeline_and_returns_indexed_count(notion_mocks):
    """One valid page is passed to the pipeline and the indexed count is returned."""
    indexed, skipped, warning = await _run_index(notion_mocks)

    assert indexed == 1
    assert skipped == 0
    assert warning is None

    notion_mocks["batch_mock"].assert_called_once()
    call_args = notion_mocks["batch_mock"].call_args
    connector_docs = call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].document_type == DocumentType.NOTION_CONNECTOR


async def test_pipeline_called_with_max_concurrency_3(notion_mocks):
    """index_batch_parallel is called with max_concurrency=3."""
    await _run_index(notion_mocks)

    call_kwargs = notion_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("max_concurrency") == 3


async def test_migrate_legacy_docs_called_before_indexing(notion_mocks):
    """migrate_legacy_docs is called on the pipeline before index_batch_parallel."""
    await _run_index(notion_mocks)

    notion_mocks["pipeline_mock"].migrate_legacy_docs.assert_called_once()


# ---------------------------------------------------------------------------
# Slice 3: Page skipping (no content / missing ID)
# ---------------------------------------------------------------------------


async def test_pages_with_missing_id_are_skipped(notion_mocks, monkeypatch):
    """Pages without page_id are skipped and not passed to the pipeline."""
    pages = [
        _make_page(page_id="valid-1"),
        {"title": "No ID page", "content": [{"type": "paragraph", "content": "text", "children": []}]},
    ]
    notion_mocks["notion_client"].get_all_pages.return_value = pages

    _, skipped, _ = await _run_index(notion_mocks)

    connector_docs = notion_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].unique_id == "valid-1"
    assert skipped == 1


async def test_pages_with_no_content_are_skipped(notion_mocks, monkeypatch):
    """Pages with empty content are skipped."""
    pages = [
        _make_page(page_id="valid-1"),
        _make_page(page_id="empty-1", content=[]),
    ]
    notion_mocks["notion_client"].get_all_pages.return_value = pages

    _, skipped, _ = await _run_index(notion_mocks)

    connector_docs = notion_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 4: Duplicate content skipping
# ---------------------------------------------------------------------------


async def test_duplicate_content_pages_are_skipped(notion_mocks, monkeypatch):
    """Pages whose content hash matches an existing document are skipped."""
    pages = [
        _make_page(page_id="new-1"),
        _make_page(page_id="dup-1"),
    ]
    notion_mocks["notion_client"].get_all_pages.return_value = pages

    call_count = 0

    async def _check_dup(session, content_hash):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            dup = MagicMock()
            dup.id = 99
            dup.document_type = "OTHER"
            return dup
        return None

    monkeypatch.setattr(_mod, "check_duplicate_document_by_hash", _check_dup)

    _, skipped, _ = await _run_index(notion_mocks)

    connector_docs = notion_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 5: Heartbeat callback forwarding
# ---------------------------------------------------------------------------


async def test_heartbeat_callback_forwarded_to_pipeline(notion_mocks):
    """on_heartbeat_callback is passed through to index_batch_parallel."""
    heartbeat_cb = AsyncMock()

    await _run_index(notion_mocks, on_heartbeat_callback=heartbeat_cb)

    call_kwargs = notion_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("on_heartbeat") is heartbeat_cb


# ---------------------------------------------------------------------------
# Slice 6: Notion-specific warning messages
# ---------------------------------------------------------------------------


async def test_skipped_ai_content_warning_in_result(notion_mocks):
    """When Notion AI content was skipped, the warning message includes it."""
    notion_mocks["notion_client"].get_skipped_content_count.return_value = 3

    _, _, warning = await _run_index(notion_mocks)

    assert warning is not None
    assert "API limitation" in warning


async def test_legacy_token_warning_in_result(notion_mocks):
    """When using legacy token, the warning message includes a notice."""
    notion_mocks["notion_client"].is_using_legacy_token.return_value = True

    _, _, warning = await _run_index(notion_mocks)

    assert warning is not None
    assert "legacy token" in warning.lower()


async def test_failed_docs_warning_in_result(notion_mocks):
    """When documents fail indexing, the warning includes the count."""
    notion_mocks["batch_mock"].return_value = ([], 0, 2)

    _, _, warning = await _run_index(notion_mocks)

    assert warning is not None
    assert "2 failed" in warning


# ---------------------------------------------------------------------------
# Slice 7: Empty pages early return
# ---------------------------------------------------------------------------


async def test_empty_pages_returns_zero_tuple(notion_mocks):
    """When no pages are found, returns (0, 0, None) and updates last_indexed."""
    notion_mocks["notion_client"].get_all_pages.return_value = []

    indexed, skipped, warning = await _run_index(notion_mocks)

    assert indexed == 0
    assert skipped == 0
    assert warning is None

    notion_mocks["batch_mock"].assert_not_called()
