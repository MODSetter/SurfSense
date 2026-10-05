from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.folders.models import Folder, FolderState
from modules.folders.names import name_key
from modules.folders.tree import MAX_DEPTH, depth

MAX_NAME = 255


def ensure_folder_path(
    session: Session, parent: Folder, segments: Sequence[str]
) -> Folder:
    """The folder at `segments` below `parent`, making whatever is missing.

    Segments past the depth cap are joined with " / " into the last level
    there is room for, so a deep tree arrives whole rather than half refused.
    """
    parts = [segment.strip() for segment in segments if segment.strip()]
    if not parts:
        return parent
    room = MAX_DEPTH - depth(session, parent.id)
    if room <= 0:
        return parent
    if len(parts) > room:
        parts = [*parts[: room - 1], " / ".join(parts[room - 1 :])]

    folder = parent
    for part in parts:
        folder = _child(session, folder, part[:MAX_NAME])
    return folder


def _child(session: Session, parent: Folder, name: str) -> Folder:
    key = name_key(name)
    existing = session.scalar(
        select(Folder).where(
            Folder.parent_id == parent.id,
            Folder.name_key == key,
            Folder.state.in_((FolderState.READY, FolderState.PLACEHOLDER)),
        )
    )
    if existing is not None:
        return existing
    child = Folder(
        workspace_id=parent.workspace_id,
        root_id=parent.root_id,
        parent_id=parent.id,
        name=name,
        name_key=key,
    )
    session.add(child)
    session.flush()
    return child
