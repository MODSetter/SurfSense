"""Path/cwd/namespace + multi-root mount-normalization tests for LIVE filesystem.

Ported from the dead-twin suites:
* ``tests/unit/middleware/test_filesystem_middleware.py`` (cwd defaults,
  relative resolution, cloud write-namespace policy)
* ``tests/unit/middleware/test_filesystem_verification.py`` (desktop
  multi-root mount-prefix normalization)

Both exercised ``app.agents.shared.middleware.filesystem`` (dead). This drives
the production free functions in
``app.agents.multi_agent_chat.shared.middleware.filesystem.middleware`` instead.
The functions only touch ``mw._filesystem_mode`` and ``mw._get_backend`` so we
pass a lightweight fake ``mw`` rather than constructing the full middleware.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.multi_agent_chat.shared.middleware.filesystem.backends.multi_root_local_folder import (
    MultiRootLocalFolderBackend,
)
from app.agents.multi_agent_chat.shared.middleware.filesystem.middleware.mode import (
    default_cwd,
)
from app.agents.multi_agent_chat.shared.middleware.filesystem.middleware.namespace_policy import (
    check_cloud_write_namespace,
)
from app.agents.multi_agent_chat.shared.middleware.filesystem.middleware.path_resolution import (
    current_cwd,
    get_contract_suggested_path,
    normalize_local_mount_path,
    resolve_relative,
)
from app.agents.shared.filesystem_selection import FilesystemMode

pytestmark = pytest.mark.unit


def _mw(mode: FilesystemMode = FilesystemMode.CLOUD, backend=None):
    return SimpleNamespace(_filesystem_mode=mode, _get_backend=lambda _rt: backend)


def _runtime(state: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(state=state or {})


# ---------------------------------------------------------------------------
# cwd defaults
# ---------------------------------------------------------------------------


class TestCwdDefaults:
    def test_default_cwd_in_cloud_is_documents_root(self):
        assert default_cwd(FilesystemMode.CLOUD) == "/documents"

    def test_default_cwd_in_desktop_is_root(self):
        assert default_cwd(FilesystemMode.DESKTOP_LOCAL_FOLDER) == "/"

    def test_current_cwd_uses_state_when_set(self):
        assert (
            current_cwd(_mw(), _runtime({"cwd": "/documents/notes"}))
            == "/documents/notes"
        )

    def test_current_cwd_falls_back_to_default(self):
        assert current_cwd(_mw(), _runtime({})) == "/documents"

    def test_current_cwd_ignores_invalid(self):
        assert current_cwd(_mw(), _runtime({"cwd": "not-absolute"})) == "/documents"


# ---------------------------------------------------------------------------
# relative resolution
# ---------------------------------------------------------------------------


class TestRelativePathResolution:
    def test_relative_path_resolves_against_cwd(self):
        assert (
            resolve_relative(_mw(), "notes.md", _runtime({"cwd": "/documents/projects"}))
            == "/documents/projects/notes.md"
        )

    def test_relative_path_with_dotdot(self):
        assert (
            resolve_relative(_mw(), "../c.md", _runtime({"cwd": "/documents/a/b"}))
            == "/documents/a/c.md"
        )

    def test_absolute_path_is_kept(self):
        assert (
            resolve_relative(_mw(), "/other/x.md", _runtime({"cwd": "/documents"}))
            == "/other/x.md"
        )

    def test_empty_path_returns_cwd(self):
        assert (
            resolve_relative(_mw(), "", _runtime({"cwd": "/documents/projects"}))
            == "/documents/projects"
        )


# ---------------------------------------------------------------------------
# contract suggested-path fallback
# ---------------------------------------------------------------------------


class TestContractSuggestedPath:
    def test_falls_back_to_documents_notes_md_in_cloud(self):
        suggested = get_contract_suggested_path(
            _mw(FilesystemMode.CLOUD),
            _runtime({"file_operation_contract": {}}),
        )
        assert suggested == "/documents/notes.md"

    def test_falls_back_to_root_notes_md_in_desktop(self):
        suggested = get_contract_suggested_path(
            _mw(FilesystemMode.DESKTOP_LOCAL_FOLDER),
            _runtime({"file_operation_contract": {}}),
        )
        assert suggested == "/notes.md"


# ---------------------------------------------------------------------------
# cloud write-namespace policy
# ---------------------------------------------------------------------------


class TestCloudWriteNamespacePolicy:
    def test_documents_path_allowed(self):
        assert (
            check_cloud_write_namespace(_mw(), "/documents/foo.md", _runtime()) is None
        )

    def test_documents_root_allowed(self):
        assert check_cloud_write_namespace(_mw(), "/documents", _runtime()) is None

    def test_temp_basename_anywhere_allowed(self):
        assert (
            check_cloud_write_namespace(_mw(), "/temp_scratch.md", _runtime()) is None
        )
        assert check_cloud_write_namespace(_mw(), "/foo/temp_x.md", _runtime()) is None
        assert (
            check_cloud_write_namespace(_mw(), "/documents/temp_x.md", _runtime())
            is None
        )

    def test_other_paths_rejected(self):
        err = check_cloud_write_namespace(_mw(), "/foo/bar.md", _runtime())
        assert err is not None
        assert "must target /documents" in err

    def test_anon_doc_path_is_read_only(self):
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
        err = check_cloud_write_namespace(_mw(), "/documents/uploaded.xml", runtime)
        assert err is not None
        assert "read-only" in err

    def test_desktop_mode_skips_namespace_policy(self):
        assert (
            check_cloud_write_namespace(
                _mw(FilesystemMode.DESKTOP_LOCAL_FOLDER), "/random/path.md", _runtime()
            )
            is None
        )


# ---------------------------------------------------------------------------
# desktop multi-root mount normalization
# ---------------------------------------------------------------------------


def _desktop_mw(backend) -> SimpleNamespace:
    return _mw(FilesystemMode.DESKTOP_LOCAL_FOLDER, backend)


class TestNormalizeLocalMountPath:
    def test_prefixes_default_mount(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            "/random-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/random-note.md"

    def test_keeps_explicit_mount(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            "/pc_backups/notes/random-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/notes/random-note.md"

    def test_windows_backslashes(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            r"\notes\random-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/notes/random-note.md"

    def test_normalizes_mixed_separators(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            r"\\notes//nested\\random-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/notes/nested/random-note.md"

    def test_keeps_explicit_mount_with_backslashes(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            r"\pc_backups\notes\random-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/notes/random-note.md"

    def test_prefixes_posix_absolute_path(self, tmp_path: Path):
        root = tmp_path / "PC Backups"
        root.mkdir()
        backend = MultiRootLocalFolderBackend((("pc_backups", str(root)),))
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            "/var/log/app.log",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/pc_backups/var/log/app.log"

    def test_prefers_unique_existing_parent_mount(self, tmp_path: Path):
        root_a = tmp_path / "RootA"
        root_b = tmp_path / "RootB"
        (root_a / "other").mkdir(parents=True)
        (root_b / "nested" / "deep").mkdir(parents=True)
        backend = MultiRootLocalFolderBackend(
            (("root_a", str(root_a)), ("root_b", str(root_b)))
        )
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            "/nested/deep/new-note.md",
            _runtime({"file_operation_contract": {}}),
        )
        assert resolved == "/root_b/nested/deep/new-note.md"

    def test_uses_suggested_mount_when_ambiguous(self, tmp_path: Path):
        root_a = tmp_path / "RootA"
        root_b = tmp_path / "RootB"
        root_a.mkdir(parents=True)
        root_b.mkdir(parents=True)
        backend = MultiRootLocalFolderBackend(
            (("root_a", str(root_a)), ("root_b", str(root_b)))
        )
        resolved = normalize_local_mount_path(
            _desktop_mw(backend),
            "/brand-new-note.md",
            _runtime(
                {"file_operation_contract": {"suggested_path": "/root_b/notes/context.md"}}
            ),
        )
        assert resolved == "/root_b/brand-new-note.md"
