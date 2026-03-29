"""Tests for Confluence indexer migrated to the unified parallel pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.connector_indexers.confluence_indexer as _mod
from app.db import DocumentType
from app.tasks.connector_indexers.confluence_indexer import (
    _build_connector_doc,
    index_confluence_pages,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_page(
    page_id: str = "p1",
    title: str = "Home",
    space_id: str = "S1",
    body: str = "<p>Hello</p>",
    comments=None,
):
    return {
        "id": page_id,
        "title": title,
        "spaceId": space_id,
        "body": {"storage": {"value": body}},
        "comments": comments or [],
    }


def _to_markdown(page: dict) -> str:
    page_title = page.get("title", "")
    page_content = page.get("body", {}).get("storage", {}).get("value", "")
    comments = page.get("comments", [])
    comments_content = ""
    if comments:
        comments_content = "\n\n## Comments\n\n"
        for comment in comments:
            comment_body = comment.get("body", {}).get("storage", {}).get("value", "")
            comment_author = comment.get("version", {}).get("authorId", "Unknown")
            comment_date = comment.get("version", {}).get("createdAt", "")
            comments_content += (
                f"**Comment by {comment_author}** ({comment_date}):\n{comment_body}\n\n"
            )
    return f"# {page_title}\n\n{page_content}{comments_content}"


# ---------------------------------------------------------------------------
# Slice 1: _build_connector_doc tracer bullet
# ---------------------------------------------------------------------------


async def test_build_connector_doc_produces_correct_fields():
    page = _make_page(
        page_id="abc-123",
        title="Engineering Handbook",
        space_id="ENG",
        comments=[{"id": "c1"}],
    )
    markdown = _to_markdown(page)

    doc = _build_connector_doc(
        page,
        markdown,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert doc.title == "Engineering Handbook"
    assert doc.unique_id == "abc-123"
    assert doc.document_type == DocumentType.CONFLUENCE_CONNECTOR
    assert doc.source_markdown == markdown
    assert doc.search_space_id == _SEARCH_SPACE_ID
    assert doc.connector_id == _CONNECTOR_ID
    assert doc.created_by_id == _USER_ID
    assert doc.should_summarize is True
    assert doc.metadata["page_id"] == "abc-123"
    assert doc.metadata["page_title"] == "Engineering Handbook"
    assert doc.metadata["space_id"] == "ENG"
    assert doc.metadata["comment_count"] == 1
    assert doc.metadata["connector_id"] == _CONNECTOR_ID
    assert doc.metadata["document_type"] == "Confluence Page"
    assert doc.metadata["connector_type"] == "Confluence"
    assert doc.fallback_summary is not None
    assert "Engineering Handbook" in doc.fallback_summary
    assert markdown in doc.fallback_summary


async def test_build_connector_doc_summary_disabled():
    doc = _build_connector_doc(
        _make_page(),
        _to_markdown(_make_page()),
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=False,
    )
    assert doc.should_summarize is False


# ---------------------------------------------------------------------------
# Shared fixtures for Slices 2-7
# ---------------------------------------------------------------------------


def _mock_connector(enable_summary: bool = True):
    c = MagicMock()
    c.config = {"access_token": "tok"}
    c.enable_summary = enable_summary
    c.last_indexed_at = None
    return c


def _mock_confluence_client(pages=None, error=None):
    client = MagicMock()
    client.get_pages_by_date_range = AsyncMock(
        return_value=(pages if pages is not None else [], error),
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def confluence_mocks(monkeypatch):
    mock_session = AsyncMock()
    mock_session.no_autoflush = MagicMock()

    mock_connector = _mock_connector()
    monkeypatch.setattr(
        _mod,
        "get_connector_by_id",
        AsyncMock(return_value=mock_connector),
    )

    confluence_client = _mock_confluence_client(pages=[_make_page()])
    monkeypatch.setattr(
        _mod,
        "ConfluenceHistoryConnector",
        MagicMock(return_value=confluence_client),
    )

    monkeypatch.setattr(
        _mod,
        "check_duplicate_document_by_hash",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        _mod,
        "update_connector_last_indexed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        _mod,
        "calculate_date_range",
        MagicMock(return_value=("2025-01-01", "2025-12-31")),
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
    mock_task_logger.log_task_progress = AsyncMock()
    mock_task_logger.log_task_success = AsyncMock()
    mock_task_logger.log_task_failure = AsyncMock()
    monkeypatch.setattr(
        _mod,
        "TaskLoggingService",
        MagicMock(return_value=mock_task_logger),
    )

    batch_mock = AsyncMock(return_value=([], 1, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.migrate_legacy_docs = AsyncMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod,
        "IndexingPipelineService",
        MagicMock(return_value=pipeline_mock),
    )

    return {
        "session": mock_session,
        "connector": mock_connector,
        "confluence_client": confluence_client,
        "task_logger": mock_task_logger,
        "pipeline_mock": pipeline_mock,
        "batch_mock": batch_mock,
    }


async def _run_index(mocks, **overrides):
    return await index_confluence_pages(
        session=mocks["session"],
        connector_id=overrides.get("connector_id", _CONNECTOR_ID),
        search_space_id=overrides.get("search_space_id", _SEARCH_SPACE_ID),
        user_id=overrides.get("user_id", _USER_ID),
        start_date=overrides.get("start_date", "2025-01-01"),
        end_date=overrides.get("end_date", "2025-12-31"),
        update_last_indexed=overrides.get("update_last_indexed", True),
        on_heartbeat_callback=overrides.get("on_heartbeat_callback"),
    )


# ---------------------------------------------------------------------------
# Slice 2: Full pipeline wiring
# ---------------------------------------------------------------------------


async def test_one_page_calls_pipeline_and_returns_indexed_count(confluence_mocks):
    indexed, skipped, warning = await _run_index(confluence_mocks)
    assert indexed == 1
    assert skipped == 0
    assert warning is None

    confluence_mocks["batch_mock"].assert_called_once()
    connector_docs = confluence_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].document_type == DocumentType.CONFLUENCE_CONNECTOR


async def test_pipeline_called_with_max_concurrency_3(confluence_mocks):
    await _run_index(confluence_mocks)
    call_kwargs = confluence_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("max_concurrency") == 3


async def test_migrate_legacy_docs_called_before_indexing(confluence_mocks):
    await _run_index(confluence_mocks)
    confluence_mocks["pipeline_mock"].migrate_legacy_docs.assert_called_once()


# ---------------------------------------------------------------------------
# Slice 3: Page skipping (missing id/title/content)
# ---------------------------------------------------------------------------


async def test_pages_with_missing_id_are_skipped(confluence_mocks):
    pages = [
        _make_page(page_id="p1", title="Valid"),
        _make_page(page_id="", title="Missing id"),
    ]
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        pages,
        None,
    )
    _, skipped, _ = await _run_index(confluence_mocks)
    connector_docs = confluence_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


async def test_pages_with_missing_title_are_skipped(confluence_mocks):
    pages = [
        _make_page(page_id="p1", title="Valid"),
        _make_page(page_id="p2", title=""),
    ]
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        pages,
        None,
    )
    _, skipped, _ = await _run_index(confluence_mocks)
    connector_docs = confluence_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


async def test_pages_with_no_content_are_skipped(confluence_mocks):
    pages = [
        _make_page(page_id="p1", title="Valid", body="<p>ok</p>"),
        _make_page(page_id="p2", title="Empty", body=""),
    ]
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        pages,
        None,
    )
    _, skipped, _ = await _run_index(confluence_mocks)
    connector_docs = confluence_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 4: Duplicate content skipping
# ---------------------------------------------------------------------------


async def test_duplicate_content_pages_are_skipped(confluence_mocks, monkeypatch):
    pages = [
        _make_page(page_id="p1", title="One"),
        _make_page(page_id="p2", title="Two"),
    ]
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        pages,
        None,
    )

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

    _, skipped, _ = await _run_index(confluence_mocks)
    connector_docs = confluence_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 5: Heartbeat callback forwarding
# ---------------------------------------------------------------------------


async def test_heartbeat_callback_forwarded_to_pipeline(confluence_mocks):
    heartbeat_cb = AsyncMock()
    await _run_index(confluence_mocks, on_heartbeat_callback=heartbeat_cb)
    call_kwargs = confluence_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("on_heartbeat") is heartbeat_cb


# ---------------------------------------------------------------------------
# Slice 6: Empty pages and no-data success tuple
# ---------------------------------------------------------------------------


async def test_empty_pages_returns_zero_tuple(confluence_mocks):
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        [],
        None,
    )
    indexed, skipped, warning = await _run_index(confluence_mocks)
    assert indexed == 0
    assert skipped == 0
    assert warning is None
    confluence_mocks["batch_mock"].assert_not_called()


async def test_no_pages_error_message_returns_success_tuple(confluence_mocks):
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        [],
        "No pages found in date range",
    )
    indexed, skipped, warning = await _run_index(confluence_mocks)
    assert indexed == 0
    assert skipped == 0
    assert warning is None


async def test_api_error_still_returns_3_tuple(confluence_mocks):
    confluence_mocks["confluence_client"].get_pages_by_date_range.return_value = (
        [],
        "API exploded",
    )
    result = await _run_index(confluence_mocks)
    assert len(result) == 3
    assert result[0] == 0
    assert result[1] == 0
    assert "Failed to get Confluence pages" in result[2]


# ---------------------------------------------------------------------------
# Slice 7: Failed docs warning
# ---------------------------------------------------------------------------


async def test_failed_docs_warning_in_result(confluence_mocks):
    confluence_mocks["batch_mock"].return_value = ([], 0, 2)
    _, _, warning = await _run_index(confluence_mocks)
    assert warning is not None
    assert "2 failed" in warning
