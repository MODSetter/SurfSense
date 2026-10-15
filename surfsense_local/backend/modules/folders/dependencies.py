from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.folders.models import Folder, FolderState
from modules.workspaces.dependencies import WorkspaceDep


def live_folder(session: SessionDep, workspace_id: int, folder_id: int) -> Folder:
    """A ready folder of this workspace, or 404: one being deleted takes nothing new."""
    folder = session.get(Folder, folder_id)
    if (
        folder is None
        or folder.workspace_id != workspace_id
        or folder.state is not FolderState.READY
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    return folder


def get_folder(folder_id: int, workspace: WorkspaceDep, session: SessionDep) -> Folder:
    return live_folder(session, workspace.id, folder_id)


FolderDep = Annotated[Folder, Depends(get_folder)]
