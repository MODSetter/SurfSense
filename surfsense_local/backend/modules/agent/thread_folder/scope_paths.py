"""The mirrored paths of some of a workspace's sources, read from their rows and the live folders."""

import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.agent.thread_folder.mirror_path import (
    LiveFolder,
    MirroredSource,
    lay_out,
)


def scope_paths(
    session: Session, workspace_id: int, ids: Iterable[int], base: Path
) -> dict[int, PurePosixPath]:
    """Each of `ids` that exists in the workspace, by its path under `base` (a `sources/`)."""
    rows = session.execute(
        text(
            "SELECT id, title, folder_id FROM documents WHERE workspace_id = :ws "
            "AND id IN (SELECT value FROM json_each(:ids))"
        ),
        {"ws": workspace_id, "ids": json.dumps(list(ids))},
    ).all()
    folders = session.execute(
        text(
            "SELECT id, parent_id, name FROM folders WHERE workspace_id = :ws "
            "AND state IN ('ready', 'placeholder')"
        ),
        {"ws": workspace_id},
    ).all()
    return lay_out(
        str(base),
        [MirroredSource(row.id, row.title, row.folder_id) for row in rows],
        [LiveFolder(row.id, row.parent_id, row.name) for row in folders],
    )
