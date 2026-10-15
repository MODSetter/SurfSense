from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.source_roots.managed_root import ensure_managed_root
from modules.workspaces.models import Workspace


def ensure_default_workspace(session: Session) -> None:
    """A local install always owns one workspace to open into on first launch."""
    if session.scalar(select(Workspace.id).limit(1)) is None:
        workspace = Workspace(name="My Workspace")
        session.add(workspace)
        session.flush()
        ensure_managed_root(session, workspace.id)
