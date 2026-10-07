from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.folders.models import Folder, FolderState
from modules.folders.names import name_key
from modules.folders.tree import MAX_DEPTH, depth, height, is_within
from modules.source_roots.models import SourceRoot, SourceRootKind


def require_library(session: Session, folder: Folder) -> None:
    """Folders on disk change only on disk; SurfSense never writes to them."""
    root = session.get(SourceRoot, folder.root_id)
    if root is not None and root.kind is SourceRootKind.LINKED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This folder is on disk at {root.disk_path}. "
            "Change it in your file manager.",
        )


def require_name_free(
    session: Session, parent_id: int, name: str, *, moving: int | None = None
) -> None:
    clash = session.scalar(
        select(Folder.id).where(
            Folder.parent_id == parent_id,
            Folder.name_key == name_key(name),
            Folder.state.in_((FolderState.READY, FolderState.PLACEHOLDER)),
            Folder.id != (moving or 0),
        )
    )
    if clash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"a folder named {name!r} is already there"
        )


def require_room(session: Session, parent: Folder, levels: int = 1) -> None:
    """`levels` more below `parent` must stay within the Library's depth cap."""
    if depth(session, parent.id) + levels > MAX_DEPTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"folders go at most {MAX_DEPTH} levels deep",
        )


def require_movable(session: Session, folder: Folder, parent: Folder) -> None:
    if parent.root_id != folder.root_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a folder moves only within its own root"
        )
    if is_within(session, parent.id, folder.id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "a folder cannot move into itself"
        )
    require_room(session, parent, 1 + height(session, folder.id))
