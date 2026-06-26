"""
RBAC (Role-Based Access Control) routes for managing roles, memberships, and invites.

Endpoints:
- /workspaces/{workspace_id}/roles - CRUD for roles
- /workspaces/{workspace_id}/members - CRUD for memberships
- /workspaces/{workspace_id}/invites - CRUD for invites
- /invites/{invite_code}/info - Get invite info (public)
- /invites/accept - Accept an invite
- /permissions - List all available permissions
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceInvite,
    WorkspaceMembership,
    WorkspaceRole,
    User,
    get_async_session,
)
from app.schemas import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCreate,
    InviteInfoResponse,
    InviteRead,
    InviteUpdate,
    MembershipRead,
    MembershipUpdate,
    PermissionInfo,
    PermissionsListResponse,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserWorkspaceAccess,
)
from app.users import get_auth_context
from app.utils.rbac import (
    check_permission,
    check_workspace_access,
    generate_invite_code,
    get_default_role,
    get_user_permissions,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Permissions Endpoints ============

# Human-readable descriptions for each permission
PERMISSION_DESCRIPTIONS = {
    # Documents
    "documents:create": "Add new documents, files, and content to the workspace",
    "documents:read": "View and search documents in the workspace",
    "documents:update": "Edit existing documents and their metadata",
    "documents:delete": "Remove documents from the workspace",
    # Chats
    "chats:create": "Start new AI chat conversations",
    "chats:read": "View chat history and conversations",
    "chats:update": "Edit chat titles and settings",
    "chats:delete": "Delete chat conversations",
    # Comments
    "comments:create": "Add comments and annotations to documents",
    "comments:read": "View comments on documents",
    "comments:delete": "Remove comments from documents",
    # LLM Configs
    "llm_configs:create": "Add new AI model configurations",
    "llm_configs:read": "View AI model settings and configurations",
    "llm_configs:update": "Modify AI model configurations",
    "llm_configs:delete": "Remove AI model configurations",
    # Podcasts
    "podcasts:create": "Generate new AI podcasts from content",
    "podcasts:read": "Listen to and view generated podcasts",
    "podcasts:update": "Edit podcast settings and metadata",
    "podcasts:delete": "Remove generated podcasts",
    # Connectors
    "connectors:create": "Set up new data source integrations",
    "connectors:read": "View configured data sources and their status",
    "connectors:update": "Modify data source configurations",
    "connectors:delete": "Remove data source integrations",
    # Logs
    "logs:read": "View activity logs and audit trail",
    "logs:delete": "Clear activity logs",
    # Members
    "members:invite": "Send invitations to new team members",
    "members:view": "View the list of team members",
    "members:remove": "Remove members from the workspace",
    "members:manage_roles": "Assign and change member roles",
    # Roles
    "roles:create": "Create new custom roles",
    "roles:read": "View available roles and their permissions",
    "roles:update": "Modify role permissions",
    "roles:delete": "Remove custom roles",
    # Settings
    "settings:view": "View workspace settings",
    "settings:update": "Modify workspace settings",
    "settings:delete": "Delete the entire workspace",
    # API access
    "api_access:manage": "Enable or disable programmatic API access for a workspace",
    # Automations
    "automations:create": "Create automations from chat or JSON",
    "automations:read": "View automations, their triggers, and run history",
    "automations:update": "Edit automations and manage their triggers",
    "automations:delete": "Remove automations from the workspace",
    "automations:execute": "Manually fire automations",
    # Full access
    "*": "Full access to all features and settings",
}


@router.get("/permissions", response_model=PermissionsListResponse)
async def list_all_permissions(
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all available permissions that can be assigned to roles.
    """
    permissions = []
    for perm in Permission:
        # Extract category from permission value (e.g., "documents:read" -> "documents")
        category = perm.value.split(":")[0] if ":" in perm.value else "general"
        description = PERMISSION_DESCRIPTIONS.get(
            perm.value, f"Permission for {perm.value}"
        )

        permissions.append(
            PermissionInfo(
                value=perm.value,
                name=perm.name,
                category=category,
                description=description,
            )
        )

    return PermissionsListResponse(permissions=permissions)


# ============ Role Endpoints ============


@router.post(
    "/workspaces/{workspace_id}/roles",
    response_model=RoleRead,
)
async def create_role(
    workspace_id: int,
    role_data: RoleCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Create a new custom role in a workspace.
    Requires ROLES_CREATE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_CREATE.value,
            "You don't have permission to create roles",
        )

        # Check if role with same name already exists
        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.workspace_id == workspace_id,
                WorkspaceRole.name == role_data.name,
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A role with name '{role_data.name}' already exists in this workspace",
            )

        # Validate permissions
        valid_permissions = {p.value for p in Permission}
        for perm in role_data.permissions:
            if perm not in valid_permissions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid permission: {perm}",
                )

        # If setting is_default to True, unset any existing default
        if role_data.is_default:
            await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.is_default == True,  # noqa: E712
                )
            )
            existing_defaults = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.is_default == True,  # noqa: E712
                )
            )
            for existing in existing_defaults.scalars().all():
                existing.is_default = False

        db_role = WorkspaceRole(
            **role_data.model_dump(),
            workspace_id=workspace_id,
            is_system_role=False,
        )
        session.add(db_role)
        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create role: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/roles",
    response_model=list[RoleRead],
)
async def list_roles(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all roles in a workspace.
    Requires ROLES_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_READ.value,
            "You don't have permission to view roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.workspace_id == workspace_id
            )
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch roles: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/roles/{role_id}",
    response_model=RoleRead,
)
async def get_role(
    workspace_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific role by ID.
    Requires ROLES_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_READ.value,
            "You don't have permission to view roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        role = result.scalars().first()

        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        return role

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch role: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/roles/{role_id}",
    response_model=RoleRead,
)
async def update_role(
    workspace_id: int,
    role_id: int,
    role_update: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a role.
    Requires ROLES_UPDATE permission.
    System roles can only have their permissions updated, not name/description.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_UPDATE.value,
            "You don't have permission to update roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        db_role = result.scalars().first()

        if not db_role:
            raise HTTPException(status_code=404, detail="Role not found")

        update_data = role_update.model_dump(exclude_unset=True)

        # System roles have restrictions on what can be updated
        if db_role.is_system_role:
            # Can only update permissions for system roles
            restricted_fields = {"name", "description", "is_default"}
            if any(field in update_data for field in restricted_fields):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot modify name, description, or default status of system roles",
                )

        # Check for name conflict if updating name
        if "name" in update_data and update_data["name"] != db_role.name:
            existing = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.name == update_data["name"],
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"A role with name '{update_data['name']}' already exists",
                )

        # Validate permissions if provided
        if "permissions" in update_data:
            valid_permissions = {p.value for p in Permission}
            for perm in update_data["permissions"]:
                if perm not in valid_permissions:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid permission: {perm}",
                    )

        # Handle is_default change
        if update_data.get("is_default") and not db_role.is_default:
            # Unset existing default
            existing_defaults = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.is_default == True,  # noqa: E712
                )
            )
            for existing in existing_defaults.scalars().all():
                existing.is_default = False

        for key, value in update_data.items():
            setattr(db_role, key, value)

        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update role: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/roles/{role_id}")
async def delete_role(
    workspace_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a custom role.
    Requires ROLES_DELETE permission.
    System roles cannot be deleted.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_DELETE.value,
            "You don't have permission to delete roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        db_role = result.scalars().first()

        if not db_role:
            raise HTTPException(status_code=404, detail="Role not found")

        if db_role.is_system_role:
            raise HTTPException(
                status_code=400,
                detail="System roles cannot be deleted",
            )

        await session.delete(db_role)
        await session.commit()
        return {"message": "Role deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete role: {e!s}"
        ) from e


# ============ Membership Endpoints ============


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[MembershipRead],
)
async def list_members(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all members of a workspace.
    Requires MEMBERS_VIEW permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_VIEW.value,
            "You don't have permission to view members",
        )

        result = await session.execute(
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.role))
            .filter(WorkspaceMembership.workspace_id == workspace_id)
        )
        memberships = result.scalars().all()

        # Fetch user emails for each membership
        response = []
        for membership in memberships:
            user_result = await session.execute(
                select(User).filter(User.id == membership.user_id)
            )
            member_user = user_result.scalars().first()

            membership_dict = {
                "id": membership.id,
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "role_id": membership.role_id,
                "is_owner": membership.is_owner,
                "joined_at": membership.joined_at,
                "created_at": membership.created_at,
                "role": membership.role,
                "user_email": member_user.email if member_user else None,
                "user_display_name": member_user.display_name if member_user else None,
                "user_avatar_url": member_user.avatar_url if member_user else None,
                "user_last_login": member_user.last_login if member_user else None,
            }
            response.append(membership_dict)

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch members: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/members/{membership_id}",
    response_model=MembershipRead,
)
async def update_member_role(
    workspace_id: int,
    membership_id: int,
    membership_update: MembershipUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a member's role.
    Requires MEMBERS_MANAGE_ROLES permission.
    Cannot change owner's role.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_MANAGE_ROLES.value,
            "You don't have permission to manage member roles",
        )

        result = await session.execute(
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.role))
            .filter(
                WorkspaceMembership.id == membership_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(status_code=404, detail="Membership not found")

        # Cannot change owner's role
        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Cannot change the owner's role",
            )

        # Verify the new role exists in this workspace
        if membership_update.role_id:
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == membership_update.role_id,
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        db_membership.role_id = membership_update.role_id
        await session.commit()
        await session.refresh(db_membership)

        # Fetch user email
        user_result = await session.execute(
            select(User).filter(User.id == db_membership.user_id)
        )
        member_user = user_result.scalars().first()

        return {
            "id": db_membership.id,
            "user_id": db_membership.user_id,
            "workspace_id": db_membership.workspace_id,
            "role_id": db_membership.role_id,
            "is_owner": db_membership.is_owner,
            "joined_at": db_membership.joined_at,
            "created_at": db_membership.created_at,
            "role": db_membership.role,
            "user_email": member_user.email if member_user else None,
            "user_last_login": member_user.last_login if member_user else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update member role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update member role: {e!s}"
        ) from e


# NOTE: /members/me must be defined BEFORE /members/{membership_id}
# because FastAPI matches routes in order, and "me" would otherwise
# be interpreted as a membership_id (causing a 422 validation error)
@router.delete("/workspaces/{workspace_id}/members/me")
async def leave_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Leave a workspace (remove own membership).
    Owners cannot leave their workspace.
    """
    try:
        result = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(
                status_code=404,
                detail="You are not a member of this workspace",
            )

        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Owners cannot leave their workspace. Transfer ownership first or delete the workspace.",
            )

        await session.delete(db_membership)
        await session.commit()
        return {"message": "Successfully left the workspace"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to leave workspace: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to leave workspace: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/members/{membership_id}")
async def remove_member(
    workspace_id: int,
    membership_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Remove a member from a workspace.
    Requires MEMBERS_REMOVE permission.
    Cannot remove the owner.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_REMOVE.value,
            "You don't have permission to remove members",
        )

        result = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.id == membership_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(status_code=404, detail="Membership not found")

        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the owner from the workspace",
            )

        await session.delete(db_membership)
        await session.commit()
        return {"message": "Member removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to remove member: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to remove member: {e!s}"
        ) from e


# ============ Invite Endpoints ============


@router.post(
    "/workspaces/{workspace_id}/invites",
    response_model=InviteRead,
)
async def create_invite(
    workspace_id: int,
    invite_data: InviteCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create a new invite link for a workspace.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to create invites",
        )

        # Verify role exists if specified
        if invite_data.role_id:
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == invite_data.role_id,
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        db_invite = WorkspaceInvite(
            **invite_data.model_dump(),
            invite_code=generate_invite_code(),
            workspace_id=workspace_id,
            created_by_id=user.id,
        )
        session.add(db_invite)
        await session.commit()

        # Reload with role
        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(WorkspaceInvite.id == db_invite.id)
        )
        db_invite = result.scalars().first()

        return db_invite

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create invite: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all invites for a workspace.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to view invites",
        )

        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(WorkspaceInvite.workspace_id == workspace_id)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch invites: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/invites/{invite_id}",
    response_model=InviteRead,
)
async def update_invite(
    workspace_id: int,
    invite_id: int,
    invite_update: InviteUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update an invite.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to update invites",
        )

        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(
                WorkspaceInvite.id == invite_id,
                WorkspaceInvite.workspace_id == workspace_id,
            )
        )
        db_invite = result.scalars().first()

        if not db_invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        update_data = invite_update.model_dump(exclude_unset=True)

        # Verify role exists if updating role_id
        if update_data.get("role_id"):
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == update_data["role_id"],
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        for key, value in update_data.items():
            setattr(db_invite, key, value)

        await session.commit()
        await session.refresh(db_invite)
        return db_invite

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update invite: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def revoke_invite(
    workspace_id: int,
    invite_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Revoke (delete) an invite.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to revoke invites",
        )

        result = await session.execute(
            select(WorkspaceInvite).filter(
                WorkspaceInvite.id == invite_id,
                WorkspaceInvite.workspace_id == workspace_id,
            )
        )
        db_invite = result.scalars().first()

        if not db_invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        await session.delete(db_invite)
        await session.commit()
        return {"message": "Invite revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to revoke invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to revoke invite: {e!s}"
        ) from e


# ============ Public Invite Endpoints ============


@router.get("/invites/{invite_code}/info", response_model=InviteInfoResponse)
async def get_invite_info(
    invite_code: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get information about an invite (public endpoint, no auth required).
    Returns minimal info for displaying on invite acceptance page.
    """
    try:
        result = await session.execute(
            select(WorkspaceInvite)
            .options(
                selectinload(WorkspaceInvite.role),
                selectinload(WorkspaceInvite.workspace),
            )
            .filter(WorkspaceInvite.invite_code == invite_code)
        )
        invite = result.scalars().first()

        if not invite:
            return InviteInfoResponse(
                workspace_name="",
                role_name=None,
                is_valid=False,
                message="Invite not found",
            )

        # Check if invite is still valid
        if not invite.is_active:
            return InviteInfoResponse(
                workspace_name=invite.workspace.name
                if invite.workspace
                else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite is no longer active",
            )

        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            return InviteInfoResponse(
                workspace_name=invite.workspace.name
                if invite.workspace
                else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite has expired",
            )

        if invite.max_uses and invite.uses_count >= invite.max_uses:
            return InviteInfoResponse(
                workspace_name=invite.workspace.name
                if invite.workspace
                else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite has reached its maximum uses",
            )

        return InviteInfoResponse(
            workspace_name=invite.workspace.name if invite.workspace else "",
            role_name=invite.role.name if invite.role else "Default",
            is_valid=True,
        )

    except Exception as e:
        logger.error(f"Failed to get invite info: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get invite info: {e!s}"
        ) from e


@router.post("/invites/accept", response_model=InviteAcceptResponse)
async def accept_invite(
    request: InviteAcceptRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Accept an invite and join a workspace.
    """
    try:
        result = await session.execute(
            select(WorkspaceInvite)
            .options(
                selectinload(WorkspaceInvite.role),
                selectinload(WorkspaceInvite.workspace),
            )
            .filter(WorkspaceInvite.invite_code == request.invite_code)
        )
        invite = result.scalars().first()

        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        # Validate invite
        if not invite.is_active:
            raise HTTPException(
                status_code=400, detail="This invite is no longer active"
            )

        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=400, detail="This invite has expired")

        if invite.max_uses and invite.uses_count >= invite.max_uses:
            raise HTTPException(
                status_code=400, detail="This invite has reached its maximum uses"
            )

        # Check if user is already a member
        existing_membership = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == invite.workspace_id,
            )
        )
        if existing_membership.scalars().first():
            raise HTTPException(
                status_code=400,
                detail="You are already a member of this workspace",
            )

        # Determine role to assign
        role_id = invite.role_id
        if not role_id:
            # Use default role
            default_role = await get_default_role(session, invite.workspace_id)
            role_id = default_role.id if default_role else None

        # Create membership
        membership = WorkspaceMembership(
            user_id=user.id,
            workspace_id=invite.workspace_id,
            role_id=role_id,
            is_owner=False,
            invited_by_invite_id=invite.id,
        )
        session.add(membership)

        # Increment invite usage
        invite.uses_count += 1

        await session.commit()

        role_name = invite.role.name if invite.role else "Default"
        workspace_name = invite.workspace.name if invite.workspace else ""

        return InviteAcceptResponse(
            message="Successfully joined the workspace",
            workspace_id=invite.workspace_id,
            workspace_name=workspace_name,
            role_name=role_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to accept invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to accept invite: {e!s}"
        ) from e


# ============ User Access Info ============


@router.get(
    "/workspaces/{workspace_id}/my-access",
    response_model=UserWorkspaceAccess,
)
async def get_my_access(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Get the current user's access info for a workspace.
    """
    try:
        membership = await check_workspace_access(session, auth, workspace_id)

        # Get workspace name
        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()

        # Get permissions
        permissions = await get_user_permissions(session, user.id, workspace_id)

        return UserWorkspaceAccess(
            workspace_id=workspace_id,
            workspace_name=workspace.name if workspace else "",
            is_owner=membership.is_owner,
            role_name=membership.role.name if membership.role else None,
            permissions=permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get access info: {e!s}"
        ) from e
