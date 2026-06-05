"""Cloud-mode ``rm``/``rmdir`` staging tests for the LIVE filesystem middleware.

Ported from the former ``tests/unit/agents/new_chat/test_rm_rmdir_cloud.py``,
which exercised the *dead twin* ``app.agents.shared.middleware.filesystem``.
This drives the production decomposed tools
(``app.agents.multi_agent_chat.shared.middleware.filesystem``) instead: it
builds the real middleware via ``build_filesystem_mw``, pulls the real ``rm`` /
``rmdir`` tools off it, and invokes their coroutines with a stubbed
``KBPostgresBackend`` + runtime so we can assert the end-of-turn staging
payloads (``pending_deletes`` / ``pending_dir_deletes``) and the destructive-op
guard rails (root, /documents, anon doc, non-empty, cwd/ancestor, file vs dir).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.multi_agent_chat.shared.middleware.filesystem import (
    build_filesystem_mw,
)
from app.agents.multi_agent_chat.shared.state.reducers import _CLEAR
from app.agents.shared.filesystem_backends import build_backend_resolver
from app.agents.shared.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.shared.middleware.kb_postgres_backend import KBPostgresBackend

pytestmark = pytest.mark.unit


def _make_middleware(mode: FilesystemMode = FilesystemMode.CLOUD):
    selection = FilesystemSelection(mode=mode)
    resolver = build_backend_resolver(selection, search_space_id=1)
    return build_filesystem_mw(
        backend_resolver=resolver,
        filesystem_mode=mode,
        search_space_id=1,
        user_id="00000000-0000-0000-0000-000000000001",
        thread_id=1,
    )


def _tool(mw, name: str):
    return next(t for t in mw.tools if t.name == name)


def _runtime(state: dict[str, Any] | None = None, *, tool_call_id: str = "tc-abc"):
    state = state or {}
    state.setdefault("cwd", "/documents")
    return SimpleNamespace(state=state, tool_call_id=tool_call_id)


class _KBBackendStub(KBPostgresBackend):
    """Construct-able ``KBPostgresBackend`` subclass for tests.

    Bypasses the real ``__init__`` (which expects a runtime + DB session) and
    injects only the async methods the rm/rmdir tools touch. The class
    inheritance keeps the ``isinstance(backend, KBPostgresBackend)`` checks in
    the tools on the cloud path.
    """

    def __init__(self, *, children=None, file_data=None) -> None:
        self.als_info = AsyncMock(return_value=children or [])
        self._load_file_data = AsyncMock(
            return_value=(file_data, 17) if file_data is not None else None
        )


def _make_backend_stub(*, children=None, file_data=None) -> KBPostgresBackend:
    return _KBBackendStub(children=children, file_data=file_data)


def _bind_backend(mw, backend):
    mw._get_backend = lambda runtime: backend
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

        result = await _tool(m, "rm").coroutine("/documents/notes.md", runtime=runtime)

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
        result = await _tool(m, "rm").coroutine("/documents", runtime=_runtime())
        assert isinstance(result, str)
        assert "refusing to rm" in result

    @pytest.mark.asyncio
    async def test_rejects_root(self):
        m = _make_middleware()
        result = await _tool(m, "rm").coroutine("/", runtime=_runtime())
        assert isinstance(result, str)
        assert "refusing to rm" in result

    @pytest.mark.asyncio
    async def test_rejects_directory_via_staged_dirs(self):
        m = _make_middleware()
        runtime = _runtime({"staged_dirs": ["/documents/team-x"]})
        result = await _tool(m, "rm").coroutine("/documents/team-x", runtime=runtime)
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
        result = await _tool(m, "rm").coroutine("/documents/foo", runtime=_runtime())
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
        result = await _tool(m, "rm").coroutine(
            "/documents/uploaded.xml", runtime=runtime
        )
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
        result = await _tool(m, "rm").coroutine("/documents/notes.md", runtime=runtime)
        dirty = result.update.get("dirty_paths") or []
        # First element is the _CLEAR sentinel; the rm'd path must not survive.
        assert "/documents/notes.md" not in dirty[1:]


# ---------------------------------------------------------------------------
# rmdir
# ---------------------------------------------------------------------------


class TestRmdirStaging:
    @pytest.mark.asyncio
    async def test_stages_dir_delete_when_empty_and_db_backed(self):
        m = _make_middleware()
        backend = _bind_backend(m, _make_backend_stub(children=[]))
        backend._load_file_data = AsyncMock(return_value=None)
        backend.als_info = AsyncMock(
            side_effect=[
                [],  # children of /documents/proj
                [{"path": "/documents/proj", "is_dir": True}],  # parent listing
            ]
        )
        runtime = _runtime({"cwd": "/documents"}, tool_call_id="tc-rd")

        result = await _tool(m, "rmdir").coroutine("/documents/proj", runtime=runtime)

        assert hasattr(result, "update")
        assert result.update["pending_dir_deletes"] == [
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
        result = await _tool(m, "rmdir").coroutine(
            "/documents/proj", runtime=_runtime()
        )
        assert isinstance(result, str)
        assert "not empty" in result

    @pytest.mark.asyncio
    async def test_unstages_same_turn_mkdir(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[]))
        runtime = _runtime(
            {"cwd": "/documents", "staged_dirs": ["/documents/scratch"]},
            tool_call_id="tc-rd",
        )
        result = await _tool(m, "rmdir").coroutine(
            "/documents/scratch", runtime=runtime
        )

        assert hasattr(result, "update")
        update = result.update
        assert "pending_dir_deletes" not in update
        staged_after = update["staged_dirs"]
        assert staged_after[0] == _CLEAR
        assert "/documents/scratch" not in staged_after[1:]

    @pytest.mark.asyncio
    async def test_rejects_root_and_documents(self):
        m = _make_middleware()
        for victim in ("/", "/documents"):
            result = await _tool(m, "rmdir").coroutine(victim, runtime=_runtime())
            assert isinstance(result, str)
            assert "refusing to rmdir" in result

    @pytest.mark.asyncio
    async def test_rejects_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/proj"})
        result = await _tool(m, "rmdir").coroutine("/documents/proj", runtime=runtime)
        assert isinstance(result, str)
        assert "cwd" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_ancestor_of_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/proj/sub"})
        result = await _tool(m, "rmdir").coroutine("/documents/proj", runtime=runtime)
        assert isinstance(result, str)
        assert "cwd" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_files(self):
        m = _make_middleware()
        _bind_backend(m, _make_backend_stub(children=[], file_data={"content": ["x"]}))
        result = await _tool(m, "rmdir").coroutine(
            "/documents/notes.md", runtime=_runtime()
        )
        assert isinstance(result, str)
        assert "is a file" in result


# ---------------------------------------------------------------------------
# KBPostgresBackend staged-delete view filter (already the live backend)
# ---------------------------------------------------------------------------


class TestKBPostgresBackendDeleteFilter:
    """``als_info`` / glob / grep must suppress paths queued for delete."""

    def _make_backend(self, state: dict[str, Any]) -> KBPostgresBackend:
        runtime = SimpleNamespace(state=state)
        return KBPostgresBackend(search_space_id=1, runtime=runtime)

    def test_pending_filesystem_view_returns_deleted_paths(self):
        backend = self._make_backend(
            {
                "pending_deletes": [{"path": "/documents/x.md", "tool_call_id": "t1"}],
                "pending_dir_deletes": [
                    {"path": "/documents/d1", "tool_call_id": "t2"}
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
