"""Tests for page limit enforcement in connector indexers.

Covers:
  A) PageLimitService.estimate_pages_from_metadata — pure function (no mocks)
  B) Page-limit quota gating in _index_selected_files tested through the
     real PageLimitService with a mock DB session (system boundary).
     Google Drive is the primary, with OneDrive/Dropbox smoke tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.page_limit_service import PageLimitService

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTOR_ID = 42
_SEARCH_SPACE_ID = 1


# ===================================================================
# A) PageLimitService.estimate_pages_from_metadata — pure function
#    No mocks: it's a staticmethod with no I/O.
# ===================================================================


class TestEstimatePagesFromMetadata:
    """Vertical slices for the page estimation staticmethod."""

    def test_pdf_100kb_returns_1(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", 100 * 1024) == 1

    def test_pdf_500kb_returns_5(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", 500 * 1024) == 5

    def test_pdf_1mb(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", 1024 * 1024) == 10

    def test_docx_50kb_returns_1(self):
        assert PageLimitService.estimate_pages_from_metadata(".docx", 50 * 1024) == 1

    def test_docx_200kb(self):
        assert PageLimitService.estimate_pages_from_metadata(".docx", 200 * 1024) == 4

    def test_pptx_uses_200kb_per_page(self):
        assert PageLimitService.estimate_pages_from_metadata(".pptx", 600 * 1024) == 3

    def test_xlsx_uses_100kb_per_page(self):
        assert PageLimitService.estimate_pages_from_metadata(".xlsx", 300 * 1024) == 3

    def test_txt_uses_3000_bytes_per_page(self):
        assert PageLimitService.estimate_pages_from_metadata(".txt", 9000) == 3

    def test_image_always_returns_1(self):
        for ext in (".jpg", ".png", ".gif", ".webp"):
            assert PageLimitService.estimate_pages_from_metadata(ext, 5_000_000) == 1

    def test_audio_uses_1mb_per_page(self):
        assert (
            PageLimitService.estimate_pages_from_metadata(".mp3", 3 * 1024 * 1024) == 3
        )

    def test_video_uses_5mb_per_page(self):
        assert (
            PageLimitService.estimate_pages_from_metadata(".mp4", 15 * 1024 * 1024) == 3
        )

    def test_unknown_ext_uses_80kb_per_page(self):
        assert PageLimitService.estimate_pages_from_metadata(".xyz", 160 * 1024) == 2

    def test_zero_size_returns_1(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", 0) == 1

    def test_negative_size_returns_1(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", -500) == 1

    def test_minimum_is_always_1(self):
        assert PageLimitService.estimate_pages_from_metadata(".pdf", 50) == 1

    def test_epub_uses_50kb_per_page(self):
        assert PageLimitService.estimate_pages_from_metadata(".epub", 250 * 1024) == 5


# ===================================================================
# B) Page-limit enforcement in connector indexers
#    System boundary mocked: DB session (for PageLimitService)
#    System boundary mocked: external API clients, download/ETL
#    NOT mocked: PageLimitService itself (our own code)
# ===================================================================


class _FakeUser:
    """Stands in for the User ORM model at the DB boundary."""

    def __init__(self, pages_used: int = 0, pages_limit: int = 100):
        self.pages_used = pages_used
        self.pages_limit = pages_limit


def _make_page_limit_session(pages_used: int = 0, pages_limit: int = 100):
    """Build a mock DB session that real PageLimitService can operate against.

    Every ``session.execute()`` returns a result compatible with both
    ``get_page_usage`` (.first() → tuple) and ``update_page_usage``
    (.unique().scalar_one_or_none() → User-like).
    """
    fake_user = _FakeUser(pages_used, pages_limit)
    session = AsyncMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.first.return_value = (fake_user.pages_used, fake_user.pages_limit)
        result.unique.return_value.scalar_one_or_none.return_value = fake_user
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


def _make_gdrive_file(file_id: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": "application/octet-stream",
        "size": str(size),
    }


# ---------------------------------------------------------------------------
# Google Drive: _index_selected_files
# ---------------------------------------------------------------------------


@pytest.fixture
def gdrive_selected_mocks(monkeypatch):
    """Mocks for Google Drive _index_selected_files — only system boundaries."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_id):
        return get_file_results.get(file_id, (None, f"Not configured: {file_id}"))

    monkeypatch.setattr(_mod, "get_file_by_id", _fake_get_file)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )

    return {
        "mod": _mod,
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_gdrive_selected(mocks, file_ids):
    from app.tasks.connector_indexers.google_drive_indexer import (
        _index_selected_files,
    )

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_ids,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )


async def test_gdrive_files_within_quota_are_downloaded(gdrive_selected_mocks):
    """Files whose cumulative estimated pages fit within remaining quota
    are sent to _download_and_index."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2", "f3"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (3, 0)

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz")]
    )

    assert indexed == 3
    assert errors == []
    call_files = m["download_and_index_mock"].call_args[0][2]
    assert len(call_files) == 3


async def test_gdrive_files_exceeding_quota_rejected(gdrive_selected_mocks):
    """Files whose pages would exceed remaining quota are rejected."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 98
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["big"] = (
        _make_gdrive_file("big", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(m, [("big", "huge.pdf")])

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_gdrive_quota_mix_partial_indexing(gdrive_selected_mocks):
    """3rd file pushes over quota → only first two indexed."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 2

    for fid in ("f1", "f2", "f3"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz")]
    )

    assert indexed == 2
    assert len(errors) == 1
    call_files = m["download_and_index_mock"].call_args[0][2]
    assert {f["id"] for f in call_files} == {"f1", "f2"}


async def test_gdrive_proportional_page_deduction(gdrive_selected_mocks):
    """Pages deducted are proportional to successfully indexed files."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2", "f3", "f4"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 2)

    await _run_gdrive_selected(
        m,
        [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz"), ("f4", "f4.xyz")],
    )

    assert m["fake_user"].pages_used == 2


async def test_gdrive_no_deduction_when_nothing_indexed(gdrive_selected_mocks):
    """If batch_indexed == 0, user's pages_used stays unchanged."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 5
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["f1"] = (
        _make_gdrive_file("f1", "f1.xyz", size=80 * 1024),
        None,
    )
    m["download_and_index_mock"].return_value = (0, 1)

    await _run_gdrive_selected(m, [("f1", "f1.xyz")])

    assert m["fake_user"].pages_used == 5


async def test_gdrive_zero_quota_rejects_all(gdrive_selected_mocks):
    """When pages_used == pages_limit, every file is rejected."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 100
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz")]
    )

    assert indexed == 0
    assert len(errors) == 2


# ---------------------------------------------------------------------------
# Google Drive: _index_full_scan
# ---------------------------------------------------------------------------


@pytest.fixture
def gdrive_full_scan_mocks(monkeypatch):
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 0, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )
    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock())
    )

    return {
        "mod": _mod,
        "session": session,
        "fake_user": fake_user,
        "task_logger": mock_task_logger,
        "download_mock": download_mock,
        "batch_mock": batch_mock,
    }


async def _run_gdrive_full_scan(mocks, max_files=500):
    from app.tasks.connector_indexers.google_drive_indexer import _index_full_scan

    return await _index_full_scan(
        MagicMock(),
        mocks["session"],
        MagicMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "folder-root",
        "My Folder",
        mocks["task_logger"],
        MagicMock(),
        max_files,
        include_subfolders=False,
        enable_summary=True,
    )


async def test_gdrive_full_scan_skips_over_quota(gdrive_full_scan_mocks, monkeypatch):
    m = gdrive_full_scan_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 2

    page_files = [
        _make_gdrive_file(f"f{i}", f"file{i}.xyz", size=80 * 1024) for i in range(5)
    ]
    monkeypatch.setattr(
        m["mod"],
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )
    m["download_mock"].return_value = ([], 0)
    m["batch_mock"].return_value = ([], 2, 0)

    _indexed, skipped, _unsup = await _run_gdrive_full_scan(m)

    call_files = m["download_mock"].call_args[0][1]
    assert len(call_files) == 2
    assert skipped == 3


async def test_gdrive_full_scan_deducts_after_indexing(
    gdrive_full_scan_mocks, monkeypatch
):
    m = gdrive_full_scan_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    page_files = [
        _make_gdrive_file(f"f{i}", f"file{i}.xyz", size=80 * 1024) for i in range(3)
    ]
    monkeypatch.setattr(
        m["mod"],
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )
    mock_docs = [MagicMock() for _ in range(3)]
    m["download_mock"].return_value = (mock_docs, 0)
    m["batch_mock"].return_value = ([], 3, 0)

    await _run_gdrive_full_scan(m)

    assert m["fake_user"].pages_used == 3


# ---------------------------------------------------------------------------
# Google Drive: _index_with_delta_sync
# ---------------------------------------------------------------------------


async def test_gdrive_delta_sync_skips_over_quota(monkeypatch):
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, _ = _make_page_limit_session(0, 2)

    changes = [
        {
            "fileId": f"mod{i}",
            "file": _make_gdrive_file(f"mod{i}", f"mod{i}.xyz", size=80 * 1024),
        }
        for i in range(5)
    ]
    monkeypatch.setattr(
        _mod,
        "fetch_all_changes",
        AsyncMock(return_value=(changes, "new-token", None)),
    )
    monkeypatch.setattr(_mod, "categorize_change", lambda change: "modified")
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 2, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )
    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock())
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    _indexed, skipped, _unsupported = await _mod._index_with_delta_sync(
        MagicMock(),
        session,
        MagicMock(),
        _CONNECTOR_ID,
        _SEARCH_SPACE_ID,
        _USER_ID,
        "folder-root",
        "start-token",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    call_files = download_mock.call_args[0][1]
    assert len(call_files) == 2
    assert skipped == 3


# ===================================================================
# C) OneDrive smoke tests — verify page limit wiring
# ===================================================================


def _make_onedrive_file(file_id: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": file_id,
        "name": name,
        "file": {"mimeType": "application/octet-stream"},
        "size": str(size),
        "lastModifiedDateTime": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def onedrive_selected_mocks(monkeypatch):
    import app.tasks.connector_indexers.onedrive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_id):
        return get_file_results.get(file_id, (None, f"Not found: {file_id}"))

    monkeypatch.setattr(_mod, "get_file_by_id", _fake_get_file)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )

    return {
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_onedrive_selected(mocks, file_ids):
    from app.tasks.connector_indexers.onedrive_indexer import _index_selected_files

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_ids,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )


async def test_onedrive_over_quota_rejected(onedrive_selected_mocks):
    """OneDrive: files exceeding quota produce errors, not downloads."""
    m = onedrive_selected_mocks
    m["fake_user"].pages_used = 99
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["big"] = (
        _make_onedrive_file("big", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_onedrive_selected(m, [("big", "huge.pdf")])

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_onedrive_deducts_after_success(onedrive_selected_mocks):
    """OneDrive: pages_used increases after successful indexing."""
    m = onedrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2"):
        m["get_file_results"][fid] = (
            _make_onedrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    await _run_onedrive_selected(m, [("f1", "f1.xyz"), ("f2", "f2.xyz")])

    assert m["fake_user"].pages_used == 2


# ===================================================================
# D) Dropbox smoke tests — verify page limit wiring
# ===================================================================


def _make_dropbox_file(file_path: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": f"id:{file_path}",
        "name": name,
        ".tag": "file",
        "path_lower": file_path,
        "size": str(size),
        "server_modified": "2026-01-01T00:00:00Z",
        "content_hash": f"hash_{name}",
    }


@pytest.fixture
def dropbox_selected_mocks(monkeypatch):
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_path):
        return get_file_results.get(file_path, (None, f"Not found: {file_path}"))

    monkeypatch.setattr(_mod, "get_file_by_path", _fake_get_file)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )

    return {
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_dropbox_selected(mocks, file_paths):
    from app.tasks.connector_indexers.dropbox_indexer import _index_selected_files

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_paths,
        connector_id=_CONNECTOR_ID,
        search_space_id=_SEARCH_SPACE_ID,
        user_id=_USER_ID,
        enable_summary=True,
    )


async def test_dropbox_over_quota_rejected(dropbox_selected_mocks):
    """Dropbox: files exceeding quota produce errors, not downloads."""
    m = dropbox_selected_mocks
    m["fake_user"].pages_used = 99
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["/huge.pdf"] = (
        _make_dropbox_file("/huge.pdf", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_dropbox_selected(
        m, [("/huge.pdf", "huge.pdf")]
    )

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_dropbox_deducts_after_success(dropbox_selected_mocks):
    """Dropbox: pages_used increases after successful indexing."""
    m = dropbox_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for name in ("f1.xyz", "f2.xyz"):
        path = f"/{name}"
        m["get_file_results"][path] = (
            _make_dropbox_file(path, name, size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    await _run_dropbox_selected(m, [("/f1.xyz", "f1.xyz"), ("/f2.xyz", "f2.xyz")])

    assert m["fake_user"].pages_used == 2
