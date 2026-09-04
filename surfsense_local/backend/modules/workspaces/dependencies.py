from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.workspaces.models import Workspace


def get_workspace(workspace_id: int, session: SessionDep) -> Workspace:
    """Resolve the workspace in the path, or fail the request before the handler."""
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")

    return workspace


WorkspaceDep = Annotated[Workspace, Depends(get_workspace)]
