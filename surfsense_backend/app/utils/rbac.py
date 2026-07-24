"""
RBAC (Role-Based Access Control) utility functions.
Provides helpers for checking user permissions in workspaces.
"""

import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    has_permission,
)


async def get_user_membership(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: int,
) -> WorkspaceMembership | None:
    """
    Get the user's membership in a workspace.

    Args:
        session: Database session
        user_id: User UUID
        workspace_id: Workspace ID

    Returns:
        WorkspaceMembership if found, None otherwise
    """
    result = await session.execute(
        select(WorkspaceMembership)
        .options(selectinload(WorkspaceMembership.role))
        .filter(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    return result.scalars().first()


async def get_user_permissions(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: int,
) -> list[str]:
    """
    Get the user's permissions in a workspace.

    Args:
        session: Database session
        user_id: User UUID
        workspace_id: Workspace ID

    Returns:
        List of permission strings
    """
    membership = await get_user_membership(session, user_id, workspace_id)

    if not membership:
        return []

    # Owners always have full access
    if membership.is_owner:
        return [Permission.FULL_ACCESS.value]

    # Get permissions from role
    if membership.role:
        return membership.role.permissions or []

    return []


async def get_allowed_read_space_ids(
    session: AsyncSession,
    auth: AuthContext,
) -> list[int]:
    """Return workspaces the principal may read through sync transports.

    This mirrors the basic REST workspace access rule: membership is required,
    and PAT principals are additionally constrained by the per-space API gate.
    """
    stmt = (
        select(WorkspaceMembership.workspace_id)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .filter(WorkspaceMembership.user_id == auth.user.id)
        .order_by(WorkspaceMembership.workspace_id)
    )
    if auth.is_gated:
        stmt = stmt.filter(Workspace.api_access_enabled == True)  # noqa: E712

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _enforce_api_access_gate(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    workspace: Workspace | None = None,
) -> Workspace:
    if workspace is None:
        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if auth.is_gated and not workspace.api_access_enabled:
        raise HTTPException(
            status_code=403,
            detail="API access is not enabled for this workspace.",
        )

    return workspace


async def check_permission(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    required_permission: str,
    error_message: str = "You don't have permission to perform this action",
) -> WorkspaceMembership:
    """
    Check if a user has a specific permission in a workspace.
    Raises HTTPException if permission is denied.

    Args:
        session: Database session
        user: User object
        workspace_id: Workspace ID
        required_permission: Permission string to check
        error_message: Custom error message for permission denied

    Returns:
        WorkspaceMembership if permission granted

    Raises:
        HTTPException: If user doesn't have access or permission
    """
    membership = await get_user_membership(session, auth.user.id, workspace_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this workspace",
        )

    # Get user's permissions
    if membership.is_owner:
        permissions = [Permission.FULL_ACCESS.value]
    elif membership.role:
        permissions = membership.role.permissions or []
    else:
        permissions = []

    if not has_permission(permissions, required_permission):
        raise HTTPException(status_code=403, detail=error_message)

    await _enforce_api_access_gate(session, auth, workspace_id)

    return membership


async def check_workspace_access(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> WorkspaceMembership:
    """
    Check if a user has any access to a workspace.
    This is used for basic access control (user is a member).

    Args:
        session: Database session
        user: User object
        workspace_id: Workspace ID

    Returns:
        WorkspaceMembership if user has access

    Raises:
        HTTPException: If user doesn't have access
    """
    membership = await get_user_membership(session, auth.user.id, workspace_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this workspace",
        )

    await _enforce_api_access_gate(session, auth, workspace_id)

    return membership


async def is_workspace_owner(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: int,
) -> bool:
    """
    Check if a user is the owner of a workspace.

    Args:
        session: Database session
        user_id: User UUID
        workspace_id: Workspace ID

    Returns:
        True if user is the owner, False otherwise
    """
    membership = await get_user_membership(session, user_id, workspace_id)
    return membership is not None and membership.is_owner


async def get_workspace_with_access_check(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    required_permission: str | None = None,
) -> tuple[Workspace, WorkspaceMembership]:
    """
    Get a workspace with access and optional permission check.

    Args:
        session: Database session
        user: User object
        workspace_id: Workspace ID
        required_permission: Optional permission to check

    Returns:
        Tuple of (Workspace, WorkspaceMembership)

    Raises:
        HTTPException: If workspace not found or user lacks access/permission
    """
    # Get the workspace
    result = await session.execute(
        select(Workspace).filter(Workspace.id == workspace_id)
    )
    workspace = result.scalars().first()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check access
    if required_permission:
        membership = await check_permission(
            session, auth, workspace_id, required_permission
        )
    else:
        membership = await check_workspace_access(session, auth, workspace_id)

    await _enforce_api_access_gate(session, auth, workspace_id, workspace)

    return workspace, membership


def generate_invite_code() -> str:
    """
    Generate a unique invite code for workspace invites.

    Returns:
        A 32-character URL-safe invite code
    """
    return secrets.token_urlsafe(24)


async def get_default_role(
    session: AsyncSession,
    workspace_id: int,
) -> WorkspaceRole | None:
    """
    Get the default role for a workspace (used when accepting invites without a specific role).

    Args:
        session: Database session
        workspace_id: Workspace ID

    Returns:
        Default WorkspaceRole or None
    """
    result = await session.execute(
        select(WorkspaceRole).filter(
            WorkspaceRole.workspace_id == workspace_id,
            WorkspaceRole.is_default == True,  # noqa: E712
        )
    )
    return result.scalars().first()


async def get_owner_role(
    session: AsyncSession,
    workspace_id: int,
) -> WorkspaceRole | None:
    """
    Get the Owner role for a workspace.

    Args:
        session: Database session
        workspace_id: Workspace ID

    Returns:
        Owner WorkspaceRole or None
    """
    result = await session.execute(
        select(WorkspaceRole).filter(
            WorkspaceRole.workspace_id == workspace_id,
            WorkspaceRole.name == "Owner",
        )
    )
    return result.scalars().first()
