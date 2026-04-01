"""Tests for parallel download + indexing in the Dropbox indexer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import DocumentType
from app.tasks.connector_indexers.dropbox_indexer import (
    _download_files_parallel,
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
