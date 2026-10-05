from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from api.dependencies import SessionDep
from api.notify import notify_changed
from modules.events.dependencies import EventBrokerDep
from modules.events.schemas import EventKind
from modules.folders.cancel_folder import cancel_folder
from modules.folders.delete_folder import delete_folder, summarize
from modules.folders.dependencies import FolderDep, live_folder
from modules.folders.models import Folder, FolderState
from modules.folders.move_documents import move_documents
from modules.folders.names import name_key
from modules.folders.placement import (
    require_library,
    require_movable,
    require_name_free,
    require_room,
)
from modules.folders.schemas import (
    CancelOutcome,
    DocumentMove,
    FolderCreate,
    FolderRead,
    FolderSummary,
    FolderUpdate,
    MoveOutcome,
)
from modules.source_roots.managed_root import ensure_managed_root
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["folders"])


@router.get(
    "/folders",
    response_model=list[FolderRead],
    summary="List every folder of a workspace, roots' own folders included",
)
def list_folders(workspace: WorkspaceDep, session: SessionDep) -> Sequence[Folder]:
    ensure_managed_root(session, workspace.id)
    return session.scalars(
        select(Folder)
        .where(
            Folder.workspace_id == workspace.id,
            Folder.state.in_((FolderState.READY, FolderState.PLACEHOLDER)),
        )
        .order_by(Folder.parent_id.is_not(None), Folder.name_key, Folder.id)
    ).all()


@router.post(
    "/folders",
    response_model=FolderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Make a folder",
)
def create_folder(
    payload: FolderCreate,
    workspace: WorkspaceDep,
    session: SessionDep,
    broker: EventBrokerDep,
) -> Folder:
    parent = (
        live_folder(session, workspace.id, payload.parent_id)
        if payload.parent_id is not None
        else ensure_managed_root(session, workspace.id)
    )
    require_library(session, parent)
    require_room(session, parent)
    require_name_free(session, parent.id, payload.name)
    folder = Folder(
        workspace_id=workspace.id,
        root_id=parent.root_id,
        parent_id=parent.id,
        name=payload.name,
        name_key=name_key(payload.name),
        role=payload.role,
    )
    session.add(folder)
    session.commit()
    notify_changed(broker, workspace.id, EventKind.FOLDERS, [folder.id], "created")
    return folder


@router.patch(
    "/folders/{folder_id}",
    response_model=FolderRead,
    summary="Rename or move a folder, or set its role",
)
def update_folder(
    folder: FolderDep,
    payload: FolderUpdate,
    session: SessionDep,
    broker: EventBrokerDep,
) -> Folder:
    changes = payload.model_fields_set
    if "role" in changes:
        # A role is SurfSense's own record, so it may be set on any folder.
        folder.role = payload.role
    if changes & {"name", "parent_id"}:
        if folder.parent_id is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "a root's own folder cannot be renamed or moved",
            )
        require_library(session, folder)
    parent_id = folder.parent_id
    if payload.parent_id is not None and payload.parent_id != folder.parent_id:
        parent = live_folder(session, folder.workspace_id, payload.parent_id)
        require_movable(session, folder, parent)
        parent_id = parent.id
    name = payload.name if payload.name is not None else folder.name
    if parent_id is not None and (
        parent_id != folder.parent_id or name_key(name) != folder.name_key
    ):
        require_name_free(session, parent_id, name, moving=folder.id)
    folder.parent_id = parent_id
    folder.name = name
    folder.name_key = name_key(name)
    session.commit()
    notify_changed(
        broker, folder.workspace_id, EventKind.FOLDERS, [folder.id], "updated"
    )
    return folder


@router.get(
    "/folders/{folder_id}/summary",
    response_model=FolderSummary,
    summary="Count what deleting a folder would remove",
)
def folder_summary(folder: FolderDep, session: SessionDep) -> FolderSummary:
    return summarize(session, folder)


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a folder and every source in it, for good",
)
def remove_folder(
    folder: FolderDep, session: SessionDep, broker: EventBrokerDep
) -> Response:
    require_library(session, folder)
    workspace_id = folder.workspace_id
    documents, folders = delete_folder(session, folder)
    notify_changed(broker, workspace_id, EventKind.DOCUMENTS, documents, "deleted")
    notify_changed(broker, workspace_id, EventKind.FOLDERS, folders, "deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/folders/{folder_id}/cancel",
    response_model=CancelOutcome,
    summary="Stop every queued or running read in a folder",
)
def cancel_folder_reads(
    folder: FolderDep, session: SessionDep, broker: EventBrokerDep
) -> CancelOutcome:
    cancelled = cancel_folder(session, folder)
    session.commit()
    notify_changed(
        broker, folder.workspace_id, EventKind.DOCUMENTS, cancelled, "cancelled"
    )
    return CancelOutcome(cancelled=cancelled)


@router.post(
    "/documents/move",
    response_model=MoveOutcome,
    summary="File sources in a folder",
)
def move_documents_route(
    payload: DocumentMove,
    workspace: WorkspaceDep,
    session: SessionDep,
    broker: EventBrokerDep,
) -> MoveOutcome:
    folder = live_folder(session, workspace.id, payload.folder_id)
    require_library(session, folder)
    outcome = move_documents(session, folder, payload.document_ids)
    session.commit()
    notify_changed(broker, workspace.id, EventKind.DOCUMENTS, outcome.moved, "moved")
    return outcome
