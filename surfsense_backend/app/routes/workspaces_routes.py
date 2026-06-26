import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
    get_default_roles_config,
)
from app.schemas import (
    WorkspaceApiAccessUpdate,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithStats,
)
from app.users import allow_any_principal, get_auth_context, require_session_context
from app.utils.rbac import check_permission, check_workspace_access

logger = logging.getLogger(__name__)

router = APIRouter()


async def create_default_roles_and_membership(
    session: AsyncSession,
    workspace_id: int,
    owner_user_id,
) -> None:
    """
    Create default system roles for a workspace and add the owner as a member.

    Args:
        session: Database session
        workspace_id: The ID of the newly created workspace
        owner_user_id: The UUID of the user who created the workspace
    """
    # Create default roles
    default_roles = get_default_roles_config()
    owner_role_id = None

    for role_config in default_roles:
        db_role = WorkspaceRole(
            name=role_config["name"],
            description=role_config["description"],
            permissions=role_config["permissions"],
            is_default=role_config["is_default"],
            is_system_role=role_config["is_system_role"],
            workspace_id=workspace_id,
        )
        session.add(db_role)
        await session.flush()  # Get the ID

        if role_config["name"] == "Owner":
            owner_role_id = db_role.id

    # Create owner membership
    owner_membership = WorkspaceMembership(
        user_id=owner_user_id,
        workspace_id=workspace_id,
        role_id=owner_role_id,
        is_owner=True,
    )
    session.add(owner_membership)


@router.post("/workspaces", response_model=WorkspaceRead)
async def create_workspace(
    workspace: WorkspaceCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    user = auth.user
    try:
        workspace_data = workspace.model_dump()

        # citations_enabled defaults to True (handled by Pydantic schema)
        # qna_custom_instructions defaults to None/empty (handled by DB)

        db_workspace = Workspace(**workspace_data, user_id=user.id)
        session.add(db_workspace)
        await session.flush()  # Get the workspace ID

        # Create default roles and owner membership
        await create_default_roles_and_membership(session, db_workspace.id, user.id)

        await session.commit()
        await session.refresh(db_workspace)
        return db_workspace
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create workspace: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create workspace: {e!s}"
        ) from e


@router.get("/workspaces", response_model=list[WorkspaceWithStats])
async def read_workspaces(
    skip: int = 0,
    limit: int = 200,
    owned_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(allow_any_principal),
):
    user = auth.user
    """
    Get all workspaces the user has access to, with member count and ownership info.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        owned_only: If True, only return workspaces owned by the user.
                   If False (default), return all workspaces the user has access to.
    """
    try:
        # Exclude spaces that are pending background deletion
        not_deleting = ~Workspace.name.startswith("[DELETING] ")

        api_access_filter = (
            Workspace.api_access_enabled == True  # noqa: E712
            if auth.is_gated
            else True
        )

        if owned_only:
            # Return only workspaces where user is the original creator (user_id)
            result = await session.execute(
                select(Workspace)
                .filter(Workspace.user_id == user.id, not_deleting, api_access_filter)
                .order_by(Workspace.id.asc())
                .offset(skip)
                .limit(limit)
            )
        else:
            # Return all workspaces the user has membership in
            result = await session.execute(
                select(Workspace)
                .join(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.user_id == user.id,
                    not_deleting,
                    api_access_filter,
                )
                .order_by(Workspace.id.asc())
                .offset(skip)
                .limit(limit)
            )

        workspaces = result.scalars().all()

        # Get member counts and ownership info for each workspace
        workspaces_with_stats = []
        for space in workspaces:
            # Get member count
            count_result = await session.execute(
                select(func.count(WorkspaceMembership.id)).filter(
                    WorkspaceMembership.workspace_id == space.id
                )
            )
            member_count = count_result.scalar() or 1

            # Check if current user is owner
            ownership_result = await session.execute(
                select(WorkspaceMembership).filter(
                    WorkspaceMembership.workspace_id == space.id,
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.is_owner == True,  # noqa: E712
                )
            )
            is_owner = ownership_result.scalars().first() is not None

            workspaces_with_stats.append(
                WorkspaceWithStats(
                    id=space.id,
                    name=space.name,
                    description=space.description,
                    created_at=space.created_at,
                    user_id=space.user_id,
                    citations_enabled=space.citations_enabled,
                    api_access_enabled=space.api_access_enabled,
                    qna_custom_instructions=space.qna_custom_instructions,
                    ai_file_sort_enabled=space.ai_file_sort_enabled,
                    member_count=member_count,
                    is_owner=is_owner,
                )
            )

        return workspaces_with_stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspaces: {e!s}"
        ) from e


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def read_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific workspace by ID.
    Requires SETTINGS_VIEW permission or membership.
    """
    try:
        # Check if user has access (is a member)
        await check_workspace_access(session, auth, workspace_id)

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()

        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        return workspace

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspace: {e!s}"
        ) from e


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: int,
    workspace_update: WorkspaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a workspace.
    Requires SETTINGS_UPDATE permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update this workspace",
        )

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        update_data = workspace_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(db_workspace, key, value)
        await session.commit()
        await session.refresh(db_workspace)
        return db_workspace
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update workspace: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/api-access", response_model=WorkspaceRead
)
async def update_workspace_api_access(
    workspace_id: int,
    body: WorkspaceApiAccessUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Toggle programmatic API/PAT access for a workspace.
    Requires API_ACCESS_MANAGE permission.
    """
    try:
        if not auth.is_session:
            raise HTTPException(
                status_code=403,
                detail="This action requires an interactive session",
            )

        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.API_ACCESS_MANAGE.value,
            "You don't have permission to manage API access for this workspace",
        )

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        db_workspace.api_access_enabled = body.api_access_enabled
        await session.commit()
        await session.refresh(db_workspace)
        return db_workspace
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update API access: {e!s}"
        ) from e


@router.post("/workspaces/{workspace_id}/ai-sort")
async def trigger_ai_sort(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Trigger a full AI file sort for all documents in the workspace."""
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to trigger AI sort on this workspace",
        )

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()
        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        from app.tasks.celery_tasks.document_tasks import ai_sort_workspace_task

        ai_sort_workspace_task.delay(workspace_id, str(user.id))
        return {"message": "AI sort started"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger AI sort: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger AI sort: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}", response_model=dict)
async def delete_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a workspace.
    Requires SETTINGS_DELETE permission (only owners have this by default).

    Heavy cascade deletion (documents, chunks, threads, etc.) is dispatched
    to Celery so the response is immediate and durable across API restarts.
    """
    try:
        # Check permission - only those with SETTINGS_DELETE can delete
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_DELETE.value,
            "You don't have permission to delete this workspace",
        )

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        if (db_workspace.name or "").startswith("[DELETING] "):
            raise HTTPException(
                status_code=409,
                detail="Workspace is already being deleted.",
            )

        # Soft-delete marker (length-safe for String(100)) so users see pending state.
        prefix = "[DELETING] "
        max_len = 100
        available = max_len - len(prefix)
        base_name = db_workspace.name or ""
        db_workspace.name = f"{prefix}{base_name[:available]}"
        await session.commit()

        # Dispatch durable background deletion via Celery.
        # If queue dispatch fails, revert name to avoid stuck "[DELETING]" state.
        try:
            from app.tasks.celery_tasks.document_tasks import delete_workspace_task

            delete_workspace_task.delay(workspace_id)
        except Exception as dispatch_error:
            db_workspace.name = base_name
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail="Failed to queue background deletion. Please try again.",
            ) from dispatch_error

        return {"message": "Workspace deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete workspace: {e!s}"
        ) from e


@router.get("/workspaces/{workspace_id}/snapshots")
async def list_workspace_snapshots(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all public chat snapshots for a workspace.

    Requires PUBLIC_SHARING_VIEW permission.
    """
    from app.schemas.new_chat import PublicChatSnapshotsBySpaceResponse
    from app.services.public_chat_service import list_snapshots_for_workspace

    snapshots = await list_snapshots_for_workspace(
        session=session,
        workspace_id=workspace_id,
        auth=auth,
    )
    return PublicChatSnapshotsBySpaceResponse(snapshots=snapshots)
