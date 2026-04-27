from pathlib import Path

import pytest

from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware.filesystem import SurfSenseFilesystemMiddleware

pytestmark = pytest.mark.unit


class _BackendWithRawRead:
    def __init__(self, content: str) -> None:
        self._content = content

    def read(self, file_path: str, offset: int = 0, limit: int = 200000) -> str:
        del file_path, offset, limit
        return "     1\tline1\n     2\tline2"

    async def aread(self, file_path: str, offset: int = 0, limit: int = 200000) -> str:
        return self.read(file_path, offset, limit)

    def read_raw(self, file_path: str) -> str:
        del file_path
        return self._content

    async def aread_raw(self, file_path: str) -> str:
        return self.read_raw(file_path)


class _RuntimeNoSuggestedPath:
    state = {"file_operation_contract": {}}


class _RuntimeWithSuggestedPath:
    def __init__(self, suggested_path: str) -> None:
        self.state = {"file_operation_contract": {"suggested_path": suggested_path}}


def test_verify_written_content_prefers_raw_sync() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    expected = "line1\nline2"
    backend = _BackendWithRawRead(expected)

    verify_error = middleware._verify_written_content_sync(
        backend=backend,
        path="/note.md",
        expected_content=expected,
    )

    assert verify_error is None


def test_contract_suggested_path_falls_back_to_notes_md() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._filesystem_mode = FilesystemMode.CLOUD
    suggested = middleware._get_contract_suggested_path(_RuntimeNoSuggestedPath())  # type: ignore[arg-type]
    assert suggested == "/notes.md"


@pytest.mark.asyncio
async def test_verify_written_content_prefers_raw_async() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    expected = "line1\nline2"
    backend = _BackendWithRawRead(expected)

    verify_error = await middleware._verify_written_content_async(
        backend=backend,
        path="/note.md",
        expected_content=expected,
    )

    assert verify_error is None


def test_normalize_local_mount_path_prefixes_default_mount(tmp_path: Path) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path("/random-note.md", runtime)  # type: ignore[arg-type]

    assert resolved == "/pc_backups/random-note.md"


def test_normalize_local_mount_path_keeps_explicit_mount(tmp_path: Path) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        "/pc_backups/notes/random-note.md",
        runtime,
    )

    assert resolved == "/pc_backups/notes/random-note.md"


def test_normalize_local_mount_path_windows_backslashes(tmp_path: Path) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        r"\notes\random-note.md",
        runtime,
    )

    assert resolved == "/pc_backups/notes/random-note.md"


def test_normalize_local_mount_path_normalizes_mixed_separators(tmp_path: Path) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        r"\\notes//nested\\random-note.md",
        runtime,
    )

    assert resolved == "/pc_backups/notes/nested/random-note.md"


def test_normalize_local_mount_path_keeps_explicit_mount_with_backslashes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        r"\pc_backups\notes\random-note.md",
        runtime,
    )

    assert resolved == "/pc_backups/notes/random-note.md"


def test_normalize_local_mount_path_prefixes_posix_absolute_path_for_linux_and_macos(
    tmp_path: Path,
) -> None:
    root = tmp_path / "PC Backups"
    root.mkdir()
    backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path("/var/log/app.log", runtime)  # type: ignore[arg-type]

    assert resolved == "/pc_backups/var/log/app.log"


def test_normalize_local_mount_path_prefers_unique_existing_parent_mount(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "RootA"
    root_b = tmp_path / "RootB"
    (root_a / "other").mkdir(parents=True)
    (root_b / "nested" / "deep").mkdir(parents=True)
    backend = MultiRootLocalFolderBackend(
        (("root_a", str(root_a)), ("root_b", str(root_b)))
    )
    runtime = _RuntimeNoSuggestedPath()
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        "/nested/deep/new-note.md",
        runtime,
    )

    assert resolved == "/root_b/nested/deep/new-note.md"


def test_normalize_local_mount_path_uses_suggested_mount_when_ambiguous(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "RootA"
    root_b = tmp_path / "RootB"
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)
    backend = MultiRootLocalFolderBackend(
        (("root_a", str(root_a)), ("root_b", str(root_b)))
    )
    runtime = _RuntimeWithSuggestedPath("/root_b/notes/context.md")
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._get_backend = lambda _runtime: backend  # type: ignore[method-assign]

    resolved = middleware._normalize_local_mount_path(  # type: ignore[arg-type]
        "/brand-new-note.md",
        runtime,
    )

    assert resolved == "/root_b/brand-new-note.md"
