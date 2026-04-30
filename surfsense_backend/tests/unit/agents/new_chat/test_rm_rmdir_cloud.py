"""Cloud-mode behavior tests for the new ``rm`` and ``rmdir`` filesystem tools.

The tools build ``Command(update=...)`` payloads that the persistence
middleware applies at end of turn. These tests stub out the backend and
runtime to assert the staging payload shape:

* ``rm`` queues into ``pending_deletes`` and tombstones state files.
* ``rm`` rejects directories, ``/documents``, root, and the anonymous doc.
* ``rmdir`` queues into ``pending_dir_deletes`` and rejects non-empty dirs.
* ``rmdir`` un-stages a same-turn ``mkdir`` rather than queuing a delete.
* ``rmdir`` refuses to drop the cwd or any of its ancestors.
* ``KBPostgresBackend`` view-helpers honor staged deletes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware.filesystem import SurfSenseFilesystemMiddleware
from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend

pytestmark = pytest.mark.unit


def _make_middleware(mode: FilesystemMode = FilesystemMode.CLOUD):
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._filesystem_mode = mode
    middleware._custom_tool_descriptions = {}
    return middleware


def _runtime(state: dict[str, Any] | None = None, *, tool_call_id: str = "tc-abc"):
    state = state or {}
    state.setdefault("cwd", "/documents")
    return SimpleNamespace(state=state, tool_call_id=tool_call_id)


class _KBBackendStub(KBPostgresBackend):
    """Construct-able subclass of :class:`KBPostgresBackend` for tests.

    We bypass the real ``__init__`` (which expects a runtime + DB session)
    and inject just the methods the rm/rmdir tools touch. The class
    inheritance keeps ``isinstance(backend, KBPostgresBackend)`` checks
    inside the tools happy, which is what gates them from the desktop
    code path.
    """

    def __init__(self, *, children=None, file_data=None) -> None:
        self.als_info = AsyncMock(return_value=children or [])
        self._load_file_data = AsyncMock(
            return_value=(file_data, 17) if file_data is not None else None
        )


def _make_backend_stub(*, children=None, file_data=None) -> KBPostgresBackend:
    return _KBBackendStub(children=children, file_data=file_data)


def _bind_backend(middleware, backend):
    """Inject a backend resolver onto the middleware test instance."""
    middleware._get_backend = lambda runtime: backend
    return backend


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


class TestRmStaging:
    @pytest.mark.asyncio
    async def test_stages_delete_and_tombstones_state(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[], file_data={"content": ["x"]}))
        runtime = _runtime(
            {
                "cwd": "/documents",
                "files": {"/documents/notes.md": {"content": ["hello"]}},
                "doc_id_by_path": {"/documents/notes.md": 17},
            },
            tool_call_id="tc-1",
        )

        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents/notes.md", runtime=runtime)

        assert hasattr(result, "update"), f"expected Command, got {result!r}"
        update = result.update
        assert update["pending_deletes"] == [
            {"path": "/documents/notes.md", "tool_call_id": "tc-1"}
        ]
        assert update["files"] == {"/documents/notes.md": None}
        assert update["doc_id_by_path"] == {"/documents/notes.md": None}

    @pytest.mark.asyncio
    async def test_rejects_documents_root(self):
        m = _make_middleware()
        runtime = _runtime()
        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents", runtime=runtime)
        assert isinstance(result, str)
        assert "refusing to rm" in result

    @pytest.mark.asyncio
    async def test_rejects_root(self):
        m = _make_middleware()
        runtime = _runtime()
        tool = m._create_rm_tool()
        result = await tool.coroutine("/", runtime=runtime)
        assert isinstance(result, str)
        assert "refusing to rm" in result

    @pytest.mark.asyncio
    async def test_rejects_directory_via_staged_dirs(self):
        m = _make_middleware()
        runtime = _runtime(
            {
                "staged_dirs": ["/documents/team-x"],
            }
        )
        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents/team-x", runtime=runtime)
        assert isinstance(result, str)
        assert "directory" in result.lower()
        assert "rmdir" in result

    @pytest.mark.asyncio
    async def test_rejects_directory_via_listing(self):
        m = _make_middleware()
        _bind_backend(
            m,
            _make_backend_stub(
                children=[{"path": "/documents/foo/x.md", "is_dir": False}]
            ),
        )
        runtime = _runtime()
        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents/foo", runtime=runtime)
        assert isinstance(result, str)
        assert "directory" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_anonymous_doc(self):
        m = _make_middleware()
        runtime = _runtime(
            {
                "kb_anon_doc": {
                    "path": "/documents/uploaded.xml",
                    "title": "uploaded",
                    "content": "",
                    "chunks": [],
                }
            }
        )
        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents/uploaded.xml", runtime=runtime)
        assert isinstance(result, str)
        assert "read-only" in result

    @pytest.mark.asyncio
    async def test_drops_path_from_dirty_paths(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[], file_data={"content": ["x"]}))
        runtime = _runtime(
            {
                "files": {"/documents/notes.md": {"content": ["x"]}},
                "doc_id_by_path": {"/documents/notes.md": 17},
                "dirty_paths": ["/documents/notes.md"],
            }
        )
        tool = m._create_rm_tool()
        result = await tool.coroutine("/documents/notes.md", runtime=runtime)
        update = result.update
        # First element is _CLEAR sentinel; the rest must NOT contain the
        # rm'd path.
        dirty = update.get("dirty_paths") or []
        assert "/documents/notes.md" not in dirty[1:]


# ---------------------------------------------------------------------------
# rmdir
# ---------------------------------------------------------------------------


class TestRmdirStaging:
    @pytest.mark.asyncio
    async def test_stages_dir_delete_when_empty_and_db_backed(self):
        m = _make_middleware()
        backend = _bind_backend(m, _make_backend_stub(children=[]))
        # Override _load_file_data to return None (folder, not a file) and
        # parent listing to claim the folder exists.
        backend._load_file_data = AsyncMock(return_value=None)
        backend.als_info = AsyncMock(
            side_effect=[
                [],  # children of /documents/proj
                [
                    {"path": "/documents/proj", "is_dir": True},
                ],  # parent listing
            ]
        )
        runtime = _runtime(
            {
                "cwd": "/documents",
            },
            tool_call_id="tc-rd",
        )

        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/proj", runtime=runtime)

        assert hasattr(result, "update")
        update = result.update
        assert update["pending_dir_deletes"] == [
            {"path": "/documents/proj", "tool_call_id": "tc-rd"}
        ]

    @pytest.mark.asyncio
    async def test_rejects_non_empty(self):
        m = _make_middleware()
        _bind_backend(
            m,
            _make_backend_stub(
                children=[{"path": "/documents/proj/x.md", "is_dir": False}]
            ),
        )
        runtime = _runtime()
        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/proj", runtime=runtime)
        assert isinstance(result, str)
        assert "not empty" in result

    @pytest.mark.asyncio
    async def test_unstages_same_turn_mkdir(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[]))
        runtime = _runtime(
            {
                "cwd": "/documents",
                "staged_dirs": ["/documents/scratch"],
            },
            tool_call_id="tc-rd",
        )
        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/scratch", runtime=runtime)

        assert hasattr(result, "update")
        update = result.update
        assert "pending_dir_deletes" not in update
        # _CLEAR sentinel + remaining items (in this case, none).
        staged_after = update["staged_dirs"]
        assert staged_after[0] == "\x00__SURFSENSE_FILESYSTEM_CLEAR__\x00"
        assert "/documents/scratch" not in staged_after[1:]

    @pytest.mark.asyncio
    async def test_rejects_root(self):
        m = _make_middleware()
        runtime = _runtime()
        tool = m._create_rmdir_tool()
        for victim in ("/", "/documents"):
            result = await tool.coroutine(victim, runtime=runtime)
            assert isinstance(result, str)
            assert "refusing to rmdir" in result

    @pytest.mark.asyncio
    async def test_rejects_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/proj"})
        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/proj", runtime=runtime)
        assert isinstance(result, str)
        assert "cwd" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_ancestor_of_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/proj/sub"})
        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/proj", runtime=runtime)
        assert isinstance(result, str)
        assert "cwd" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_files(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[], file_data={"content": ["x"]}))
        runtime = _runtime()
        tool = m._create_rmdir_tool()
        result = await tool.coroutine("/documents/notes.md", runtime=runtime)
        assert isinstance(result, str)
        assert "is a file" in result


# ---------------------------------------------------------------------------
# KBPostgresBackend view filter
# ---------------------------------------------------------------------------


class TestKBPostgresBackendDeleteFilter:
    """als_info / glob / grep should suppress paths queued for delete."""

    def _make_backend(self, state: dict[str, Any]) -> KBPostgresBackend:
        runtime = SimpleNamespace(state=state)
        backend = KBPostgresBackend(search_space_id=1, runtime=runtime)
        return backend

    def test_pending_filesystem_view_returns_deleted_paths(self):
        backend = self._make_backend(
            {
                "pending_deletes": [
                    {"path": "/documents/x.md", "tool_call_id": "t1"},
                ],
                "pending_dir_deletes": [
                    {"path": "/documents/d1", "tool_call_id": "t2"},
                ],
            }
        )
        removed, alias, deleted_dirs = backend._pending_filesystem_view({})
        assert "/documents/x.md" in removed
        assert "/documents/d1" in deleted_dirs
        assert alias == {}

    def test_dir_suppressed_covers_descendants(self):
        backend = self._make_backend({})
        deleted_dirs = {"/documents/d"}
        assert backend._is_dir_suppressed("/documents/d", deleted_dirs)
        assert backend._is_dir_suppressed("/documents/d/x.md", deleted_dirs)
        assert backend._is_dir_suppressed("/documents/d/sub/y.md", deleted_dirs)
        assert not backend._is_dir_suppressed("/documents/other.md", deleted_dirs)
