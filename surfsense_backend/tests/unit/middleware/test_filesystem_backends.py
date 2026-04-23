from pathlib import Path

import pytest

from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.new_chat.middleware.local_folder_backend import LocalFolderBackend

pytestmark = pytest.mark.unit


class _RuntimeStub:
    state = {"files": {}}


def test_backend_resolver_returns_local_backend_for_local_mode(tmp_path: Path):
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        client_platform=ClientPlatform.DESKTOP,
        local_root_path=str(tmp_path),
    )
    resolver = build_backend_resolver(selection)

    backend = resolver(_RuntimeStub())
    assert isinstance(backend, LocalFolderBackend)


def test_backend_resolver_uses_cloud_mode_by_default():
    resolver = build_backend_resolver(FilesystemSelection())
    backend = resolver(_RuntimeStub())
    # StateBackend class name check keeps this test decoupled
    # from internal deepagents runtime class identity.
    assert backend.__class__.__name__ == "StateBackend"
