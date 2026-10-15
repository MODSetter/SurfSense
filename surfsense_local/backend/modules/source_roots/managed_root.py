from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.folders.models import Folder
from modules.folders.names import name_key
from modules.source_roots.models import SourceRoot, SourceRootKind

LIBRARY = "Library"


def ensure_managed_root(session: Session, workspace_id: int) -> Folder:
    """The workspace's Library root folder, made on first use."""
    root = session.scalar(
        select(SourceRoot).where(
            SourceRoot.workspace_id == workspace_id,
            SourceRoot.kind == SourceRootKind.MANAGED,
        )
    )
    if root is None:
        root = SourceRoot(
            workspace_id=workspace_id,
            kind=SourceRootKind.MANAGED,
            name=LIBRARY,
            name_key=name_key(LIBRARY),
        )
        session.add(root)
        session.flush()
    folder = session.scalar(
        select(Folder).where(Folder.root_id == root.id, Folder.parent_id.is_(None))
    )
    if folder is None:
        folder = Folder(
            workspace_id=workspace_id,
            root_id=root.id,
            name=LIBRARY,
            name_key=name_key(LIBRARY),
        )
        session.add(folder)
        session.flush()
    return folder
