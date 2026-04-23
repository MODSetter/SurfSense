from pathlib import Path

import pytest

from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)

pytestmark = pytest.mark.unit


class _RuntimeStub:
    state = {"files": {}}


def test_backend_resolver_returns_multi_root_backend_for_single_root(tmp_path: Path):
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        client_platform=ClientPlatform.DESKTOP,
        local_root_paths=(str(tmp_path),),
    )
    resolver = build_backend_resolver(selection)

    backend = resolver(_RuntimeStub())
    assert isinstance(backend, MultiRootLocalFolderBackend)


def test_backend_resolver_uses_cloud_mode_by_default():
    resolver = build_backend_resolver(FilesystemSelection())
    backend = resolver(_RuntimeStub())
    # StateBackend class name check keeps this test decoupled
    # from internal deepagents runtime class identity.
    assert backend.__class__.__name__ == "StateBackend"


def test_backend_resolver_returns_multi_root_backend_for_multiple_roots(tmp_path: Path):
    root_one = tmp_path / "resume"
    root_two = tmp_path / "notes"
    root_one.mkdir()
    root_two.mkdir()
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        client_platform=ClientPlatform.DESKTOP,
        local_root_paths=(str(root_one), str(root_two)),
    )
    resolver = build_backend_resolver(selection)

    backend = resolver(_RuntimeStub())
    assert isinstance(backend, MultiRootLocalFolderBackend)
