from pathlib import Path

import pytest

from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)

pytestmark = pytest.mark.unit


def test_mount_ids_preserve_client_mapping_order(tmp_path: Path) -> None:
    root_one = tmp_path / "PC Backups"
    root_two = tmp_path / "pc_backups"
    root_three = tmp_path / "notes@2026"
    root_one.mkdir()
    root_two.mkdir()
    root_three.mkdir()

    backend = MultiRootLocalFolderBackend(
        (
            ("pc_backups", str(root_one)),
            ("pc_backups_2", str(root_two)),
            ("notes_2026", str(root_three)),
        )
    )

    assert backend.list_mounts() == ("pc_backups", "pc_backups_2", "notes_2026")
