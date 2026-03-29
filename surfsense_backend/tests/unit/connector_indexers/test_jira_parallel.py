"""Tests for Jira indexer migrated to the unified parallel pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.connector_indexers.jira_indexer as _mod
from app.db import DocumentType
from app.tasks.connector_indexers.jira_indexer import (
    _build_connector_doc,
    index_jira_issues,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_issue(
    issue_key: str = "ENG-1",
    issue_id: str = "10001",
    title: str = "Fix login",
):
    return {"key": issue_key, "id": issue_id, "title": title}


def _make_formatted_issue(
    issue_key: str = "ENG-1",
    issue_id: str = "10001",
    title: str = "Fix login",
    status: str = "In Progress",
    priority: str = "High",
    comments=None,
):
    return {
        "key": issue_key,
        "id": issue_id,
        "title": title,
        "status": status,
        "priority": priority,
        "comments": comments or [],
    }


# ---------------------------------------------------------------------------
# Slice 1: _build_connector_doc tracer bullet
# ---------------------------------------------------------------------------


async def test_build_connector_doc_produces_correct_fields():
    issue = _make_issue(issue_key="ENG-42", issue_id="4242", title="Fix auth bug")
    formatted = _make_formatted_issue(
        issue_key="ENG-42",
        issue_id="4242",
        title="Fix auth bug",
        status="Done",
        priority="Urgent",
        comments=[{"id": "c1"}],
    )
    markdown = "# ENG-42: Fix auth bug\n\nBody"

    doc = _build_connector_doc(
        issue,
        formatted,
        markdown,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert doc.title == "ENG-42: 4242"
    assert doc.unique_id == "ENG-42"
    assert doc.document_type == DocumentType.JIRA_CONNECTOR
    assert doc.source_markdown == markdown
    assert doc.search_space_id == _SEARCH_SPACE_ID
    assert doc.connector_id == _CONNECTOR_ID
    assert doc.created_by_id == _USER_ID
    assert doc.should_summarize is True
    assert doc.metadata["issue_id"] == "ENG-42"
    assert doc.metadata["issue_identifier"] == "ENG-42"
    assert doc.metadata["issue_title"] == "4242"
    assert doc.metadata["state"] == "Done"
    assert doc.metadata["priority"] == "Urgent"
    assert doc.metadata["comment_count"] == 1
    assert doc.metadata["connector_id"] == _CONNECTOR_ID
    assert doc.metadata["document_type"] == "Jira Issue"
    assert doc.metadata["connector_type"] == "Jira"
    assert doc.fallback_summary is not None
    assert "ENG-42" in doc.fallback_summary
    assert markdown in doc.fallback_summary


async def test_build_connector_doc_summary_disabled():
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
# Shared fixtures for Slices 2-7
# ---------------------------------------------------------------------------


def _mock_connector(enable_summary: bool = True):
    c = MagicMock()
    c.config = {"access_token": "tok"}
    c.enable_summary = enable_summary
    c.last_indexed_at = None
    return c


def _mock_jira_client(issues=None, error=None):
    client = MagicMock()
    client.get_issues_by_date_range = AsyncMock(
        return_value=(issues if issues is not None else [], error),
    )
    client.format_issue = MagicMock(
        side_effect=lambda i: _make_formatted_issue(
            issue_key=i.get("key", ""),
            issue_id=i.get("id", ""),
            title=i.get("title", ""),
        )
    )
    client.format_issue_to_markdown = MagicMock(
        side_effect=lambda fi: f"# {fi.get('key', '')}: {fi.get('id', '')}\n\nContent"
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def jira_mocks(monkeypatch):
    mock_session = AsyncMock()
    mock_session.no_autoflush = MagicMock()

    mock_connector = _mock_connector()
    monkeypatch.setattr(
        _mod,
        "get_connector_by_id",
        AsyncMock(return_value=mock_connector),
    )

    jira_client = _mock_jira_client(issues=[_make_issue()])
    monkeypatch.setattr(
        _mod,
        "JiraHistoryConnector",
        MagicMock(return_value=jira_client),
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
        "jira_client": jira_client,
        "task_logger": mock_task_logger,
        "pipeline_mock": pipeline_mock,
        "batch_mock": batch_mock,
    }


async def _run_index(mocks, **overrides):
    return await index_jira_issues(
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


async def test_one_issue_calls_pipeline_and_returns_indexed_count(jira_mocks):
    indexed, skipped, warning = await _run_index(jira_mocks)
    assert indexed == 1
    assert skipped == 0
    assert warning is None

    jira_mocks["batch_mock"].assert_called_once()
    connector_docs = jira_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert connector_docs[0].document_type == DocumentType.JIRA_CONNECTOR


async def test_pipeline_called_with_max_concurrency_3(jira_mocks):
    await _run_index(jira_mocks)
    call_kwargs = jira_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("max_concurrency") == 3


async def test_migrate_legacy_docs_called_before_indexing(jira_mocks):
    await _run_index(jira_mocks)
    jira_mocks["pipeline_mock"].migrate_legacy_docs.assert_called_once()


# ---------------------------------------------------------------------------
# Slice 3: Issue skipping (missing key/title/content)
# ---------------------------------------------------------------------------


async def test_issues_with_missing_key_are_skipped(jira_mocks):
    issues = [
        _make_issue(issue_key="ENG-1", issue_id="10001"),
        {"key": "", "id": "10002", "title": "No key"},
    ]
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (issues, None)

    _, skipped, _ = await _run_index(jira_mocks)
    connector_docs = jira_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


async def test_issues_with_missing_title_are_skipped(jira_mocks):
    issues = [
        _make_issue(issue_key="ENG-1", issue_id="10001"),
        {"key": "ENG-2", "id": "", "title": "Missing id used as title"},
    ]
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (issues, None)

    _, skipped, _ = await _run_index(jira_mocks)
    connector_docs = jira_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


async def test_issues_with_no_content_are_skipped(jira_mocks):
    issues = [
        _make_issue(issue_key="ENG-1", issue_id="10001"),
        _make_issue(issue_key="ENG-2", issue_id="10002"),
    ]
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (issues, None)

    jira_mocks["jira_client"].format_issue_to_markdown.side_effect = [
        "# ENG-1: 10001\n\nContent",
        "",
    ]
    _, skipped, _ = await _run_index(jira_mocks)
    connector_docs = jira_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 4: Duplicate content skipping
# ---------------------------------------------------------------------------


async def test_duplicate_content_issues_are_skipped(jira_mocks, monkeypatch):
    issues = [
        _make_issue(issue_key="ENG-1", issue_id="10001"),
        _make_issue(issue_key="ENG-2", issue_id="10002"),
    ]
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (issues, None)

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

    _, skipped, _ = await _run_index(jira_mocks)
    connector_docs = jira_mocks["batch_mock"].call_args[0][0]
    assert len(connector_docs) == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Slice 5: Heartbeat callback forwarding
# ---------------------------------------------------------------------------


async def test_heartbeat_callback_forwarded_to_pipeline(jira_mocks):
    heartbeat_cb = AsyncMock()
    await _run_index(jira_mocks, on_heartbeat_callback=heartbeat_cb)
    call_kwargs = jira_mocks["batch_mock"].call_args[1]
    assert call_kwargs.get("on_heartbeat") is heartbeat_cb


# ---------------------------------------------------------------------------
# Slice 6: Empty issues and no-data success tuple
# ---------------------------------------------------------------------------


async def test_empty_issues_returns_zero_tuple(jira_mocks):
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = ([], None)
    indexed, skipped, warning = await _run_index(jira_mocks)
    assert indexed == 0
    assert skipped == 0
    assert warning is None
    jira_mocks["batch_mock"].assert_not_called()


async def test_no_issues_error_message_returns_success_tuple(jira_mocks):
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (
        [],
        "No issues found in date range",
    )
    indexed, skipped, warning = await _run_index(jira_mocks)
    assert indexed == 0
    assert skipped == 0
    assert warning is None


async def test_api_error_still_returns_3_tuple(jira_mocks):
    jira_mocks["jira_client"].get_issues_by_date_range.return_value = (
        [],
        "API exploded",
    )
    result = await _run_index(jira_mocks)
    assert len(result) == 3
    assert result[0] == 0
    assert result[1] == 0
    assert "Failed to get Jira issues" in result[2]


# ---------------------------------------------------------------------------
# Slice 7: Failed docs warning
# ---------------------------------------------------------------------------


async def test_failed_docs_warning_in_result(jira_mocks):
    jira_mocks["batch_mock"].return_value = ([], 0, 2)
    _, _, warning = await _run_index(jira_mocks)
    assert warning is not None
    assert "2 failed" in warning
