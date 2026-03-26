"""Tests for parallel download + indexing in the Google Drive indexer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.connector_indexers.google_drive_indexer import (
    _download_files_parallel,
    _index_full_scan,
    _index_with_delta_sync,
)

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


def _make_file_dict(file_id: str, name: str, mime: str = "text/plain") -> dict:
    return {"id": file_id, "name": name, "mimeType": mime}


def _mock_extract_ok(file_id: str, file_name: str):
    """Return a successful (markdown, metadata, None) tuple."""
    return (
        f"# Content of {file_name}",
        {"google_drive_file_id": file_id, "google_drive_file_name": file_name},
        None,
    )


@pytest.fixture
def mock_drive_client():
    return MagicMock()


@pytest.fixture
def patch_extract(monkeypatch):
    """Provide a helper to set the download_and_extract_content mock."""
    def _patch(side_effect=None, return_value=None):
        mock = AsyncMock(side_effect=side_effect, return_value=return_value)
        monkeypatch.setattr(
            "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
            mock,
        )
        return mock
    return _patch


async def test_single_file_returns_one_connector_document(
    mock_drive_client, patch_extract,
):
    """Tracer bullet: downloading one file produces one ConnectorDocument."""
    patch_extract(return_value=_mock_extract_ok("f1", "test.txt"))

    docs, failed = await _download_files_parallel(
        mock_drive_client,
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


async def test_multiple_files_all_produce_documents(
    mock_drive_client, patch_extract,
):
    """All files are downloaded and converted to ConnectorDocuments."""
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[_mock_extract_ok(f"f{i}", f"file{i}.txt") for i in range(3)]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 3
    assert failed == 0
    assert {d.unique_id for d in docs} == {"f0", "f1", "f2"}


async def test_one_download_exception_does_not_block_others(
    mock_drive_client, patch_extract,
):
    """A RuntimeError in one download still lets the other files succeed."""
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "file0.txt"),
            RuntimeError("network timeout"),
            _mock_extract_ok("f2", "file2.txt"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 2
    assert failed == 1
    assert {d.unique_id for d in docs} == {"f0", "f2"}


async def test_etl_error_counts_as_download_failure(
    mock_drive_client, patch_extract,
):
    """download_and_extract_content returning an error is counted as failed."""
    files = [_make_file_dict("f0", "good.txt"), _make_file_dict("f1", "bad.txt")]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "good.txt"),
            (None, {}, "ETL failed"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 1
    assert failed == 1


async def test_concurrency_bounded_by_semaphore(
    mock_drive_client, monkeypatch,
):
    """Peak concurrent downloads never exceeds max_concurrency."""
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
        fid = file["id"]
        return _mock_extract_ok(fid, file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
        _slow_extract,
    )

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(6)]

    docs, failed = await _download_files_parallel(
        mock_drive_client,
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


async def test_heartbeat_fires_during_parallel_downloads(
    mock_drive_client, monkeypatch,
):
    """on_heartbeat is called at least once when downloads take time."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    monkeypatch.setattr(_mod, "HEARTBEAT_INTERVAL_SECONDS", 0)

    async def _slow_extract(client, file):
        await asyncio.sleep(0.05)
        return _mock_extract_ok(file["id"], file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
        _slow_extract,
    )

    heartbeat_calls: list[int] = []

    async def _on_heartbeat(count: int):
        heartbeat_calls.append(count)

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]

    docs, failed = await _download_files_parallel(
        mock_drive_client,
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
# Slice 6, 6b, 6c -- _index_full_scan three-phase pipeline
# ---------------------------------------------------------------------------

def _folder_dict(file_id: str, name: str) -> dict:
    return {"id": file_id, "name": name, "mimeType": "application/vnd.google-apps.folder"}


@pytest.fixture
def full_scan_mocks(mock_drive_client, monkeypatch):
    """Wire up all mocks needed to call _index_full_scan in isolation."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    mock_session = AsyncMock()
    mock_connector = MagicMock()
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()
    mock_log_entry = MagicMock()

    skip_results: dict[str, tuple[bool, str | None]] = {}

    async def _fake_skip(session, file, search_space_id):
        return skip_results.get(file["id"], (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_mock = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 0, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock),
    )

    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock()),
    )

    return {
        "drive_client": mock_drive_client,
        "session": mock_session,
        "connector": mock_connector,
        "task_logger": mock_task_logger,
        "log_entry": mock_log_entry,
        "skip_results": skip_results,
        "download_mock": download_mock,
        "batch_mock": batch_mock,
        "pipeline_mock": pipeline_mock,
    }


async def _run_full_scan(mocks, *, max_files=500, include_subfolders=False):
    return await _index_full_scan(
        mocks["drive_client"],
        mocks["session"],
        mocks["connector"],
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "folder-root",
        "My Folder",
        mocks["task_logger"],
        mocks["log_entry"],
        max_files,
        include_subfolders=include_subfolders,
        enable_summary=True,
    )


async def test_full_scan_three_phase_counts(full_scan_mocks, monkeypatch):
    """Full scan collects files serially, downloads and indexes in parallel,
    and returns correct (indexed, skipped) with renames counted as indexed."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    page_files = [
        _folder_dict("folder1", "SubFolder"),
        _make_file_dict("skip1", "unchanged.txt"),
        _make_file_dict("rename1", "renamed.txt"),
        _make_file_dict("new1", "new1.txt"),
        _make_file_dict("new2", "new2.txt"),
    ]

    monkeypatch.setattr(
        _mod, "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )

    full_scan_mocks["skip_results"]["skip1"] = (True, "unchanged")
    full_scan_mocks["skip_results"]["rename1"] = (True, "File renamed: 'old' → 'renamed.txt'")

    mock_docs = [MagicMock(), MagicMock()]
    full_scan_mocks["download_mock"].return_value = (mock_docs, 0)
    full_scan_mocks["batch_mock"].return_value = ([], 2, 0)

    indexed, skipped = await _run_full_scan(full_scan_mocks)

    assert indexed == 3  # 1 renamed + 2 from batch
    assert skipped == 1  # 1 unchanged

    full_scan_mocks["download_mock"].assert_called_once()
    call_files = full_scan_mocks["download_mock"].call_args[0][1]
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"new1", "new2"}


async def test_full_scan_respects_max_files(full_scan_mocks, monkeypatch):
    """Only max_files non-folder files are processed; the rest are ignored."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    page_files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(10)]

    monkeypatch.setattr(
        _mod, "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )

    full_scan_mocks["download_mock"].return_value = ([], 0)
    full_scan_mocks["batch_mock"].return_value = ([], 0, 0)

    await _run_full_scan(full_scan_mocks, max_files=3)

    download_call_files = full_scan_mocks["download_mock"].call_args[0][1]
    assert len(download_call_files) == 3


async def test_full_scan_uses_max_concurrency_3_for_indexing(
    full_scan_mocks, monkeypatch,
):
    """index_batch_parallel is called with max_concurrency=3."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    page_files = [_make_file_dict("f1", "file1.txt")]
    monkeypatch.setattr(
        _mod, "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )

    mock_docs = [MagicMock()]
    full_scan_mocks["download_mock"].return_value = (mock_docs, 0)
    full_scan_mocks["batch_mock"].return_value = ([], 1, 0)

    await _run_full_scan(full_scan_mocks)

    call_kwargs = full_scan_mocks["batch_mock"].call_args
    assert call_kwargs[1].get("max_concurrency") == 3 or (
        len(call_kwargs[0]) > 2 and call_kwargs[0][2] == 3
    )


# ---------------------------------------------------------------------------
# Slice 7 -- _index_with_delta_sync three-phase pipeline
# ---------------------------------------------------------------------------

async def test_delta_sync_removals_serial_rest_parallel(monkeypatch):
    """Removed/trashed changes call _remove_document; the rest go through
    _download_files_parallel and index_batch_parallel."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    changes = [
        {"fileId": "del1", "removed": True},
        {"fileId": "del2", "file": {"id": "del2", "trashed": True}},
        {"fileId": "trash1", "file": {"id": "trash1", "trashed": True}},
        {"fileId": "mod1", "file": _make_file_dict("mod1", "modified1.txt")},
        {"fileId": "mod2", "file": _make_file_dict("mod2", "modified2.txt")},
    ]

    monkeypatch.setattr(
        _mod, "fetch_all_changes",
        AsyncMock(return_value=(changes, "new-token", None)),
    )

    change_types = {
        "del1": "removed",
        "del2": "removed",
        "trash1": "trashed",
        "mod1": "modified",
        "mod2": "modified",
    }
    monkeypatch.setattr(
        _mod, "categorize_change",
        lambda change: change_types[change["fileId"]],
    )

    remove_calls: list[str] = []

    async def _fake_remove(session, file_id, search_space_id):
        remove_calls.append(file_id)

    monkeypatch.setattr(_mod, "_remove_document", _fake_remove)

    monkeypatch.setattr(
        _mod, "_should_skip_file",
        AsyncMock(return_value=(False, None)),
    )

    mock_docs = [MagicMock(), MagicMock()]
    download_mock = AsyncMock(return_value=(mock_docs, 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 2, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock),
    )
    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock()),
    )

    mock_session = AsyncMock()
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped = await _index_with_delta_sync(
        MagicMock(),
        mock_session,
        MagicMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "folder-root",
        "start-token-abc",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert sorted(remove_calls) == ["del1", "del2", "trash1"]

    download_mock.assert_called_once()
    downloaded_files = download_mock.call_args[0][1]
    assert len(downloaded_files) == 2
    assert {f["id"] for f in downloaded_files} == {"mod1", "mod2"}

    assert indexed == 2
    assert skipped == 0
