from pathlib import Path

import pytest

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware.filesystem import SurfSenseFilesystemMiddleware
from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)

pytestmark = pytest.mark.unit


class _RuntimeNoSuggestedPath:
    state = {"file_operation_contract": {}}


class _RuntimeWithSuggestedPath:
    def __init__(self, suggested_path: str) -> None:
        self.state = {"file_operation_contract": {"suggested_path": suggested_path}}


def test_contract_suggested_path_falls_back_to_documents_notes_md() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._filesystem_mode = FilesystemMode.CLOUD
    suggested = middleware._get_contract_suggested_path(_RuntimeNoSuggestedPath())  # type: ignore[arg-type]
    # Cloud default cwd is /documents so the fallback lands in the KB.
    assert suggested == "/documents/notes.md"


def test_contract_suggested_path_falls_back_to_root_notes_md_in_desktop() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._filesystem_mode = FilesystemMode.DESKTOP_LOCAL_FOLDER
    suggested = middleware._get_contract_suggested_path(_RuntimeNoSuggestedPath())  # type: ignore[arg-type]
    assert suggested == "/notes.md"


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
