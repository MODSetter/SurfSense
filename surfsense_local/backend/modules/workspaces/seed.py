from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.workspaces.models import Workspace


def ensure_default_workspace(session: Session) -> None:
    """A local install always owns one workspace to open into on first launch."""
    if session.scalar(select(Workspace.id).limit(1)) is None:
        session.add(Workspace(name="My Workspace"))
