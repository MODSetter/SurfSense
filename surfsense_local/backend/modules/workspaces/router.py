import shutil
from collections.abc import Sequence

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.workspaces.dependencies import WorkspaceDep
from modules.workspaces.models import Workspace
from modules.workspaces.schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from shared.config import get_storage_settings

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
def create_workspace(payload: WorkspaceCreate, session: SessionDep) -> Workspace:
    workspace = Workspace(name=payload.name)
    session.add(workspace)
    # The id and the timestamps are assigned by the database, and the response
    # needs them before the dependency commits.
    session.flush()
    return workspace


@router.get(
    "",
    response_model=list[WorkspaceRead],
    summary="List workspaces",
)
def list_workspaces(session: SessionDep) -> Sequence[Workspace]:
    return session.scalars(select(Workspace).order_by(Workspace.created_at)).all()


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceRead,
    summary="Read a workspace",
)
def read_workspace(workspace: WorkspaceDep) -> Workspace:
    return workspace


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceRead,
    summary="Rename a workspace",
)
def update_workspace(workspace: WorkspaceDep, payload: WorkspaceUpdate) -> Workspace:
    workspace.name = payload.name
    return workspace


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace and everything in it",
)
def delete_workspace(workspace: WorkspaceDep, session: SessionDep) -> Response:
    # One tree per workspace, removed after the commit a rollback would undo.
    directory = get_storage_settings().workspace_dir(workspace.id)

    session.delete(workspace)
    session.commit()

    shutil.rmtree(directory, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
