from pathlib import Path

import pytest

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
    LocalFilesystemMount,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.multi_root_local_folder import (
    MultiRootLocalFolderBackend,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.resolver import (
    build_backend_resolver,
)

pytestmark = pytest.mark.unit


class _RuntimeStub:
    state = {"files": {}}


def test_backend_resolver_returns_multi_root_backend_for_single_root(tmp_path: Path):
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        client_platform=ClientPlatform.DESKTOP,
        local_mounts=(LocalFilesystemMount(mount_id="tmp", root_path=str(tmp_path)),),
    )
    resolver = build_backend_resolver(selection)

    backend = resolver(_RuntimeStub())
    assert isinstance(backend, MultiRootLocalFolderBackend)
    assert backend.list_mounts() == ("tmp",)


def test_backend_resolver_uses_cloud_mode_by_default():
    resolver = build_backend_resolver(FilesystemSelection())
    backend = resolver(_RuntimeStub())
    # When no workspace_id is provided we fall back to StateBackend so
    # sub-agents / tests without DB access still work.
    assert backend.__class__.__name__ == "StateBackend"


def test_backend_resolver_uses_kb_postgres_in_cloud_with_workspace():
    resolver = build_backend_resolver(FilesystemSelection(), workspace_id=42)
    backend = resolver(_RuntimeStub())
    assert backend.__class__.__name__ == "KBPostgresBackend"
    assert backend.workspace_id == 42


def test_backend_resolver_returns_multi_root_backend_for_multiple_roots(tmp_path: Path):
    root_one = tmp_path / "resume"
    root_two = tmp_path / "notes"
    root_one.mkdir()
    root_two.mkdir()
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        client_platform=ClientPlatform.DESKTOP,
        local_mounts=(
            LocalFilesystemMount(mount_id="resume", root_path=str(root_one)),
            LocalFilesystemMount(mount_id="notes", root_path=str(root_two)),
        ),
    )
    resolver = build_backend_resolver(selection)

    backend = resolver(_RuntimeStub())
    assert isinstance(backend, MultiRootLocalFolderBackend)
    assert backend.list_mounts() == ("resume", "notes")
