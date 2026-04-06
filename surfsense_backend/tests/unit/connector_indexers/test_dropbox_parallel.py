"""Tests for parallel download + indexing in the Dropbox indexer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import DocumentType
from app.tasks.connector_indexers.dropbox_indexer import (
    _download_files_parallel,
    _index_full_scan,
    _index_selected_files,
    _index_with_delta_sync,
    index_dropbox_files,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_file_dict(file_id: str, name: str) -> dict:
    return {
        "id": file_id,
        "name": name,
        ".tag": "file",
        "path_lower": f"/{name}",
        "server_modified": "2026-01-01T00:00:00Z",
        "content_hash": f"hash_{file_id}",
    }


def _mock_extract_ok(file_id: str, file_name: str):
    return (
        f"# Content of {file_name}",
        {"dropbox_file_id": file_id, "dropbox_file_name": file_name},
        None,
    )


@pytest.fixture
def mock_dropbox_client():
    return MagicMock()


@pytest.fixture
def patch_extract(monkeypatch):
    def _patch(side_effect=None, return_value=None):
        mock = AsyncMock(side_effect=side_effect, return_value=return_value)
        monkeypatch.setattr(
            "app.tasks.connector_indexers.dropbox_indexer.download_and_extract_content",
            mock,
        )
        return mock

    return _patch


# Slice 1: Tracer bullet
async def test_single_file_returns_one_connector_document(
    mock_dropbox_client,
    patch_extract,
):
    patch_extract(return_value=_mock_extract_ok("f1", "test.txt"))

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        [_make_file_dict("f1", "test.txt")],
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 1
    assert failed == 0
    assert docs[0].title == "test.txt"
    assert docs[0].unique_id == "f1"
    assert docs[0].document_type == DocumentType.DROPBOX_FILE


# Slice 2: Multiple files all produce documents
async def test_multiple_files_all_produce_documents(
    mock_dropbox_client,
    patch_extract,
):
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[_mock_extract_ok(f"f{i}", f"file{i}.txt") for i in range(3)]
    )

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 3
    assert failed == 0
    assert {d.unique_id for d in docs} == {"f0", "f1", "f2"}


# Slice 3: Error isolation
async def test_one_download_exception_does_not_block_others(
    mock_dropbox_client,
    patch_extract,
):
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "file0.txt"),
            RuntimeError("network timeout"),
            _mock_extract_ok("f2", "file2.txt"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 2
    assert failed == 1
    assert {d.unique_id for d in docs} == {"f0", "f2"}


# Slice 4: ETL error counts as download failure
async def test_etl_error_counts_as_download_failure(
    mock_dropbox_client,
    patch_extract,
):
    files = [_make_file_dict("f0", "good.txt"), _make_file_dict("f1", "bad.txt")]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "good.txt"),
            (None, {}, "ETL failed"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 1
    assert failed == 1


# Slice 5: Semaphore bound
async def test_concurrency_bounded_by_semaphore(
    mock_dropbox_client,
    monkeypatch,
):
    lock = asyncio.Lock()
    active = 0
    peak = 0

    async def _slow_extract(client, file):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return _mock_extract_ok(file["id"], file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.dropbox_indexer.download_and_extract_content",
        _slow_extract,
    )

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(6)]

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
        max_concurrency=2,
    )

    assert len(docs) == 6
    assert failed == 0
    assert peak <= 2, f"Peak concurrency was {peak}, expected <= 2"


# Slice 6: Heartbeat fires
async def test_heartbeat_fires_during_parallel_downloads(
    mock_dropbox_client,
    monkeypatch,
):
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    monkeypatch.setattr(_mod, "HEARTBEAT_INTERVAL_SECONDS", 0)

    async def _slow_extract(client, file):
        await asyncio.sleep(0.05)
        return _mock_extract_ok(file["id"], file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.dropbox_indexer.download_and_extract_content",
        _slow_extract,
    )

    heartbeat_calls: list[int] = []

    async def _on_heartbeat(count: int):
        heartbeat_calls.append(count)

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]

    docs, failed = await _download_files_parallel(
        mock_dropbox_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
        on_heartbeat=_on_heartbeat,
    )

    assert len(docs) == 3
    assert failed == 0
    assert len(heartbeat_calls) >= 1, "Heartbeat should have fired at least once"


# ---------------------------------------------------------------------------
# D1-D2: _index_full_scan tests
# ---------------------------------------------------------------------------


def _folder_dict(name: str) -> dict:
    return {".tag": "folder", "name": name}


@pytest.fixture
def full_scan_mocks(mock_dropbox_client, monkeypatch):
    """Wire up mocks for _index_full_scan in isolation."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_session = AsyncMock()
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()
    mock_log_entry = MagicMock()

    skip_results: dict[str, tuple[bool, str | None]] = {}

    monkeypatch.setattr("app.config.config.ETL_SERVICE", "LLAMACLOUD")

    async def _fake_skip(session, file, search_space_id):
        from app.connectors.dropbox.file_types import should_skip_file as _skip
        item_skip, unsup_ext = _skip(file)
        if item_skip:
            if unsup_ext:
                return True, f"unsupported:{unsup_ext}"
            return True, "folder/non-downloadable"
        return skip_results.get(file.get("id", ""), (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    from app.services.page_limit_service import PageLimitService as _RealPLS

    mock_page_limit_instance = MagicMock()
    mock_page_limit_instance.get_page_usage = AsyncMock(return_value=(0, 999_999))
    mock_page_limit_instance.update_page_usage = AsyncMock()

    class _MockPageLimitService:
        estimate_pages_from_metadata = staticmethod(
            _RealPLS.estimate_pages_from_metadata
        )

        def __init__(self, session):
            self.get_page_usage = mock_page_limit_instance.get_page_usage
            self.update_page_usage = mock_page_limit_instance.update_page_usage

    monkeypatch.setattr(_mod, "PageLimitService", _MockPageLimitService)

    return {
        "dropbox_client": mock_dropbox_client,
        "session": mock_session,
        "task_logger": mock_task_logger,
        "log_entry": mock_log_entry,
        "skip_results": skip_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_full_scan(mocks, monkeypatch, page_files, *, max_files=500):
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    monkeypatch.setattr(
        _mod,
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None)),
    )
    return await _index_full_scan(
        mocks["dropbox_client"],
        mocks["session"],
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "",
        "Root",
        mocks["task_logger"],
        mocks["log_entry"],
        max_files,
        enable_summary=True,
    )


async def test_full_scan_three_phase_counts(full_scan_mocks, monkeypatch):
    """Skipped files excluded, renames counted as indexed, new files downloaded."""
    page_files = [
        _folder_dict("SubFolder"),
        _make_file_dict("skip1", "unchanged.txt"),
        _make_file_dict("rename1", "renamed.txt"),
        _make_file_dict("new1", "new1.txt"),
        _make_file_dict("new2", "new2.txt"),
    ]

    full_scan_mocks["skip_results"]["skip1"] = (True, "unchanged")
    full_scan_mocks["skip_results"]["rename1"] = (
        True,
        "File renamed: 'old' -> 'renamed.txt'",
    )

    full_scan_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped = await _run_full_scan(
        full_scan_mocks, monkeypatch, page_files
    )

    assert indexed == 3  # 1 renamed + 2 from batch
    assert skipped == 2  # 1 folder + 1 unchanged

    call_args = full_scan_mocks["download_and_index_mock"].call_args
    call_files = call_args[0][2]
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"new1", "new2"}


async def test_full_scan_respects_max_files(full_scan_mocks, monkeypatch):
    """Only max_files non-folder items are considered."""
    page_files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(10)]

    full_scan_mocks["download_and_index_mock"].return_value = (3, 0)

    await _run_full_scan(full_scan_mocks, monkeypatch, page_files, max_files=3)

    call_files = full_scan_mocks["download_and_index_mock"].call_args[0][2]
    assert len(call_files) == 3


# ---------------------------------------------------------------------------
# D3-D5: _index_selected_files tests
# ---------------------------------------------------------------------------


@pytest.fixture
def selected_files_mocks(mock_dropbox_client, monkeypatch):
    """Wire up mocks for _index_selected_files tests."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_session = AsyncMock()

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, path):
        return get_file_results.get(path, (None, f"Not configured: {path}"))

    monkeypatch.setattr(_mod, "get_file_by_path", _fake_get_file)

    skip_results: dict[str, tuple[bool, str | None]] = {}

    async def _fake_skip(session, file, search_space_id):
        return skip_results.get(file["id"], (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    from app.services.page_limit_service import PageLimitService as _RealPLS

    mock_page_limit_instance = MagicMock()
    mock_page_limit_instance.get_page_usage = AsyncMock(return_value=(0, 999_999))
    mock_page_limit_instance.update_page_usage = AsyncMock()

    class _MockPageLimitService:
        estimate_pages_from_metadata = staticmethod(
            _RealPLS.estimate_pages_from_metadata
        )

        def __init__(self, session):
            self.get_page_usage = mock_page_limit_instance.get_page_usage
            self.update_page_usage = mock_page_limit_instance.update_page_usage

    monkeypatch.setattr(_mod, "PageLimitService", _MockPageLimitService)

    return {
        "dropbox_client": mock_dropbox_client,
        "session": mock_session,
        "get_file_results": get_file_results,
        "skip_results": skip_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_selected(mocks, file_tuples):
    return await _index_selected_files(
        mocks["dropbox_client"],
        mocks["session"],
        file_tuples,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )


async def test_selected_files_single_file_indexed(selected_files_mocks):
    selected_files_mocks["get_file_results"]["/report.pdf"] = (
        _make_file_dict("f1", "report.pdf"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (1, 0)

    indexed, skipped, errors = await _run_selected(
        selected_files_mocks,
        [("/report.pdf", "report.pdf")],
    )

    assert indexed == 1
    assert skipped == 0
    assert errors == []


async def test_selected_files_fetch_failure_isolation(selected_files_mocks):
    selected_files_mocks["get_file_results"]["/first.txt"] = (
        _make_file_dict("f1", "first.txt"),
        None,
    )
    selected_files_mocks["get_file_results"]["/mid.txt"] = (None, "HTTP 404")
    selected_files_mocks["get_file_results"]["/third.txt"] = (
        _make_file_dict("f3", "third.txt"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, errors = await _run_selected(
        selected_files_mocks,
        [("/first.txt", "first.txt"), ("/mid.txt", "mid.txt"), ("/third.txt", "third.txt")],
    )

    assert indexed == 2
    assert skipped == 0
    assert len(errors) == 1
    assert "mid.txt" in errors[0]


async def test_selected_files_skip_rename_counting(selected_files_mocks):
    for path, fid, fname in [
        ("/unchanged.txt", "s1", "unchanged.txt"),
        ("/renamed.txt", "r1", "renamed.txt"),
        ("/new1.txt", "n1", "new1.txt"),
        ("/new2.txt", "n2", "new2.txt"),
    ]:
        selected_files_mocks["get_file_results"][path] = (
            _make_file_dict(fid, fname),
            None,
        )

    selected_files_mocks["skip_results"]["s1"] = (True, "unchanged")
    selected_files_mocks["skip_results"]["r1"] = (
        True,
        "File renamed: 'old' -> 'renamed.txt'",
    )
    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, errors = await _run_selected(
        selected_files_mocks,
        [
            ("/unchanged.txt", "unchanged.txt"),
            ("/renamed.txt", "renamed.txt"),
            ("/new1.txt", "new1.txt"),
            ("/new2.txt", "new2.txt"),
        ],
    )

    assert indexed == 3  # 1 renamed + 2 batch
    assert skipped == 1
    assert errors == []

    mock = selected_files_mocks["download_and_index_mock"]
    call_files = mock.call_args[0][2]
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"n1", "n2"}


# ---------------------------------------------------------------------------
# E1-E4: _index_with_delta_sync tests
# ---------------------------------------------------------------------------


async def test_delta_sync_deletions_call_remove_document(monkeypatch):
    """E1: deleted entries are processed via _remove_document."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        {".tag": "deleted", "name": "gone.txt", "path_lower": "/gone.txt", "id": "id:del1"},
        {".tag": "deleted", "name": "also_gone.pdf", "path_lower": "/also_gone.pdf", "id": "id:del2"},
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "new-cursor", None))

    remove_calls: list[str] = []

    async def _fake_remove(session, file_id, search_space_id):
        remove_calls.append(file_id)

    monkeypatch.setattr(_mod, "_remove_document", _fake_remove)
    monkeypatch.setattr(_mod, "_download_and_index", AsyncMock(return_value=(0, 0)))

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert sorted(remove_calls) == ["id:del1", "id:del2"]
    assert cursor == "new-cursor"


async def test_delta_sync_upserts_filtered_and_downloaded(monkeypatch):
    """E2: modified/new file entries go through skip filter then download+index."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        _make_file_dict("mod1", "modified1.txt"),
        _make_file_dict("mod2", "modified2.txt"),
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "cursor-v2", None))

    monkeypatch.setattr(_mod, "_should_skip_file", AsyncMock(return_value=(False, None)))

    download_mock = AsyncMock(return_value=(2, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_mock)

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "cursor-v1",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert indexed == 2
    assert skipped == 0
    assert cursor == "cursor-v2"

    downloaded_files = download_mock.call_args[0][2]
    assert len(downloaded_files) == 2
    assert {f["id"] for f in downloaded_files} == {"mod1", "mod2"}


async def test_delta_sync_mix_deletions_and_upserts(monkeypatch):
    """E3: deletions processed, then remaining upserts filtered and indexed."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        {".tag": "deleted", "name": "removed.txt", "path_lower": "/removed.txt", "id": "id:del1"},
        {".tag": "deleted", "name": "trashed.pdf", "path_lower": "/trashed.pdf", "id": "id:del2"},
        _make_file_dict("mod1", "updated.txt"),
        _make_file_dict("new1", "brandnew.docx"),
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "final-cursor", None))

    remove_calls: list[str] = []

    async def _fake_remove(session, file_id, search_space_id):
        remove_calls.append(file_id)

    monkeypatch.setattr(_mod, "_remove_document", _fake_remove)
    monkeypatch.setattr(_mod, "_should_skip_file", AsyncMock(return_value=(False, None)))

    download_mock = AsyncMock(return_value=(2, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_mock)

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert sorted(remove_calls) == ["id:del1", "id:del2"]
    assert indexed == 2
    assert skipped == 0
    assert cursor == "final-cursor"

    downloaded_files = download_mock.call_args[0][2]
    assert {f["id"] for f in downloaded_files} == {"mod1", "new1"}


async def test_delta_sync_returns_new_cursor(monkeypatch):
    """E4: the new cursor from the API response is returned."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=([], "brand-new-cursor-xyz", None))

    monkeypatch.setattr(_mod, "_download_and_index", AsyncMock(return_value=(0, 0)))

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert cursor == "brand-new-cursor-xyz"
    assert indexed == 0
    assert skipped == 0


# ---------------------------------------------------------------------------
# F1-F3: index_dropbox_files orchestrator tests
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator_mocks(monkeypatch):
    """Wire up mocks for index_dropbox_files orchestrator tests."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_connector = MagicMock()
    mock_connector.config = {"_token_encrypted": False}
    mock_connector.last_indexed_at = None
    mock_connector.enable_summary = True

    monkeypatch.setattr(
        _mod,
        "get_connector_by_id",
        AsyncMock(return_value=mock_connector),
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
    mock_task_logger.log_task_progress = AsyncMock()
    mock_task_logger.log_task_success = AsyncMock()
    mock_task_logger.log_task_failure = AsyncMock()
    monkeypatch.setattr(
        _mod, "TaskLoggingService", MagicMock(return_value=mock_task_logger)
    )

    monkeypatch.setattr(_mod, "update_connector_last_indexed", AsyncMock())

    full_scan_mock = AsyncMock(return_value=(5, 2))
    monkeypatch.setattr(_mod, "_index_full_scan", full_scan_mock)

    delta_sync_mock = AsyncMock(return_value=(3, 1, "delta-cursor-new"))
    monkeypatch.setattr(_mod, "_index_with_delta_sync", delta_sync_mock)

    mock_client = MagicMock()
    mock_client.get_latest_cursor = AsyncMock(return_value=("latest-cursor-abc", None))
    monkeypatch.setattr(
        _mod, "DropboxClient", MagicMock(return_value=mock_client)
    )

    return {
        "connector": mock_connector,
        "full_scan_mock": full_scan_mock,
        "delta_sync_mock": delta_sync_mock,
        "mock_client": mock_client,
    }


async def test_orchestrator_uses_delta_sync_when_cursor_and_last_indexed(
    orchestrator_mocks,
):
    """F1: with cursor + last_indexed_at + use_delta_sync, calls delta sync."""
    from datetime import UTC, datetime

    connector = orchestrator_mocks["connector"]
    connector.config = {
        "_token_encrypted": False,
        "folder_cursors": {"/docs": "saved-cursor-123"},
    }
    connector.last_indexed_at = datetime(2026, 1, 1, tzinfo=UTC)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    indexed, skipped, error = await index_dropbox_files(
        mock_session,
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
            "indexing_options": {"use_delta_sync": True},
        },
    )

    assert error is None
    orchestrator_mocks["delta_sync_mock"].assert_called_once()
    orchestrator_mocks["full_scan_mock"].assert_not_called()


async def test_orchestrator_falls_back_to_full_scan_without_cursor(
    orchestrator_mocks,
):
    """F2: without cursor, falls back to full scan."""
    connector = orchestrator_mocks["connector"]
    connector.config = {"_token_encrypted": False}
    connector.last_indexed_at = None

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    indexed, skipped, error = await index_dropbox_files(
        mock_session,
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
            "indexing_options": {"use_delta_sync": True},
        },
    )

    assert error is None
    orchestrator_mocks["full_scan_mock"].assert_called_once()
    orchestrator_mocks["delta_sync_mock"].assert_not_called()


async def test_orchestrator_persists_cursor_after_sync(orchestrator_mocks):
    """F3: after sync, persists new cursor to connector config."""
    connector = orchestrator_mocks["connector"]
    connector.config = {"_token_encrypted": False}
    connector.last_indexed_at = None

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    await index_dropbox_files(
        mock_session,
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
        },
    )

    assert "folder_cursors" in connector.config
    assert connector.config["folder_cursors"]["/docs"] == "latest-cursor-abc"
