"""Tests for Linear indexer migrated to the unified parallel pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.connector_indexers.linear_indexer as _mod
from app.db import DocumentType
from app.tasks.connector_indexers.linear_indexer import (
    _build_connector_doc,
    index_linear_issues,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_issue(
    issue_id: str = "issue-1",
    identifier: str = "ENG-1",
    title: str = "Fix bug",
):
    return {"id": issue_id, "identifier": identifier, "title": title}


def _make_formatted_issue(
    issue_id: str = "issue-1",
    identifier: str = "ENG-1",
    title: str = "Fix bug",
    state: str = "In Progress",
    priority: str = "High",
    comments=None,
):
    return {
        "id": issue_id,
        "identifier": identifier,
        "title": title,
        "state": state,
        "priority": priority,
        "description": "Some description",
        "comments": comments or [],
    }


# ---------------------------------------------------------------------------
# Slice 1: _build_connector_doc tracer bullet
# ---------------------------------------------------------------------------


async def test_build_connector_doc_produces_correct_fields():
    """Tracer bullet: a Linear issue produces a ConnectorDocument with correct fields."""
    issue = _make_issue(issue_id="abc-123", identifier="ENG-42", title="Fix login bug")
    formatted = _make_formatted_issue(
        issue_id="abc-123",
        identifier="ENG-42",
        title="Fix login bug",
        state="Done",
        priority="Urgent",
        comments=[{"id": "c1"}],
    )
    markdown = "# ENG-42: Fix login bug\n\nDescription here"

    doc = _build_connector_doc(
        issue,
        formatted,
        markdown,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert doc.title == "ENG-42: Fix login bug"
    assert doc.unique_id == "abc-123"
    assert doc.document_type == DocumentType.LINEAR_CONNECTOR
    assert doc.source_markdown == markdown
    assert doc.search_space_id == _SEARCH_SPACE_ID
    assert doc.connector_id == _CONNECTOR_ID
    assert doc.created_by_id == _USER_ID
    assert doc.should_summarize is True
    assert doc.metadata["issue_id"] == "abc-123"
    assert doc.metadata["issue_identifier"] == "ENG-42"
    assert doc.metadata["issue_title"] == "Fix login bug"
    assert doc.metadata["state"] == "Done"
    assert doc.metadata["priority"] == "Urgent"
    assert doc.metadata["comment_count"] == 1
    assert doc.metadata["connector_id"] == _CONNECTOR_ID
    assert doc.metadata["document_type"] == "Linear Issue"
    assert doc.metadata["connector_type"] == "Linear"
    assert doc.fallback_summary is not None
    assert "ENG-42" in doc.fallback_summary
    assert markdown in doc.fallback_summary


async def test_build_connector_doc_summary_disabled():
    """When enable_summary is False, should_summarize is False."""
    doc = _build_connector_doc(
        _make_issue(),
        _make_formatted_issue(),
        "# content",
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=False,
    )

    assert doc.should_summarize is False


# ---------------------------------------------------------------------------
# Shared fixtures for Slices 2-6
# ---------------------------------------------------------------------------


def _mock_connector(enable_summary: bool = True):
    c = MagicMock()
    c.config = {"access_token": "tok"}
    c.enable_summary = enable_summary
    c.last_indexed_at = None
    return c


def _mock_linear_client(issues=None, error=None):
    client = MagicMock()
    client.get_issues_by_date_range = AsyncMock(
        return_value=(issues if issues is not None else [], error),
    )
    client.format_issue = MagicMock(
        side_effect=lambda i: _make_formatted_issue(
            issue_id=i.get("id", ""),
            identifier=i.get("identifier", ""),
            title=i.get("title", ""),
        )
    )
    client.format_issue_to_markdown = MagicMock(
        side_effect=lambda fi: (
            f"# {fi.get('identifier', '')}: {fi.get('title', '')}\n\nContent"
        )
    )
    return client


@pytest.fixture
def linear_mocks(monkeypatch):
    """Wire up all external boundary mocks for index_linear_issues."""
    mock_session = AsyncMock()
    mock_session.no_autoflush = MagicMock()

    mock_connector = _mock_connector()
    monkeypatch.setattr(
        _mod,
        "get_connector_by_id",
        AsyncMock(return_value=mock_connector),
    )

    linear_client = _mock_linear_client(issues=[_make_issue()])
    monkeypatch.setattr(
        _mod,
        "LinearConnector",
        MagicMock(return_value=linear_client),
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
        "linear_client": linear_client,
        "task_logger": mock_task_logger,
        "pipeline_mock": pipeline_mock,
        "batch_mock": batch_mock,
    }


async def _run_index(mocks, **overrides):
    return await index_linear_issues(
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


async def test_one_issue_calls_pipeline_and_returns_indexed_count(linear_mocks):
    """One valid issue is passed to the pipeline and the indexed count is returned."""
    indexed, skipped, warning = await _run_index(linear_mocks)

    assert indexed == 1
    assert skipped == 0
    assert warning is None

    linear_mocks["batch_mock"].assert_called_once()
    call_args = linear_mocks["batch_mock"].call_args
    connector_docs = call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].document_type == DocumentType.LINEAR_CONNECTOR


async def test_pipeline_called_with_max_concurrency_3(linear_mocks):
    """index_batch_parallel is called with max_concurrency=3."""
    await _run_index(linear_mocks)

    call_kwargs = linear_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("max_concurrency") == 3


async def test_migrate_legacy_docs_called_before_indexing(linear_mocks):
    """migrate_legacy_docs is called on the pipeline before index_batch_parallel."""
    await _run_index(linear_mocks)

    linear_mocks["pipeline_mock"].migrate_legacy_docs.assert_called_once()


# ---------------------------------------------------------------------------
# Slice 3: Issue skipping (missing ID / title)
# ---------------------------------------------------------------------------


async def test_issues_with_missing_id_are_skipped(linear_mocks):
    """Issues without id are skipped and not passed to the pipeline."""
    issues = [
        _make_issue(issue_id="valid-1", identifier="ENG-1", title="Valid"),
        {"id": "", "identifier": "ENG-2", "title": "No ID"},
    ]
    linear_mocks["linear_client"].get_issues_by_date_range.return_value = (issues, None)

    _indexed, skipped, _ = await _run_index(linear_mocks)

    connector_docs = linear_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].unique_id == "valid-1"
    assert skipped == 1


async def test_issues_with_missing_title_are_skipped(linear_mocks):
    """Issues without title are skipped."""
    issues = [
        _make_issue(issue_id="valid-1", identifier="ENG-1", title="Valid"),
        {"id": "id-2", "identifier": "ENG-2", "title": ""},
    ]
    linear_mocks["linear_client"].get_issues_by_date_range.return_value = (issues, None)

    _indexed, skipped, _ = await _run_index(linear_mocks)

    connector_docs = linear_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 4: Duplicate content skipping
# ---------------------------------------------------------------------------


async def test_duplicate_content_issues_are_skipped(linear_mocks, monkeypatch):
    """Issues whose content hash matches an existing document are skipped."""
    issues = [
        _make_issue(issue_id="new-1", identifier="ENG-1", title="New"),
        _make_issue(issue_id="dup-1", identifier="ENG-2", title="Dup"),
    ]
    linear_mocks["linear_client"].get_issues_by_date_range.return_value = (issues, None)

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

    _indexed, skipped, _ = await _run_index(linear_mocks)

    connector_docs = linear_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 5: Heartbeat callback forwarding
# ---------------------------------------------------------------------------


async def test_heartbeat_callback_forwarded_to_pipeline(linear_mocks):
    """on_heartbeat_callback is passed through to index_batch_parallel."""
    heartbeat_cb = AsyncMock()

    await _run_index(linear_mocks, on_heartbeat_callback=heartbeat_cb)

    call_kwargs = linear_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("on_heartbeat") is heartbeat_cb


# ---------------------------------------------------------------------------
# Slice 6: Empty issues early return
# ---------------------------------------------------------------------------


async def test_empty_issues_returns_zero_tuple(linear_mocks):
    """When no issues are found, returns (0, 0, None) and pipeline is not called."""
    linear_mocks["linear_client"].get_issues_by_date_range.return_value = ([], None)

    indexed, skipped, warning = await _run_index(linear_mocks)

    assert indexed == 0
    assert skipped == 0
    assert warning is None

    linear_mocks["batch_mock"].assert_not_called()


async def test_failed_docs_warning_in_result(linear_mocks):
    """When documents fail indexing, the warning includes the count."""
    linear_mocks["batch_mock"].return_value = ([], 0, 2)

    _, _, warning = await _run_index(linear_mocks)

    assert warning is not None
    assert "2 failed" in warning
