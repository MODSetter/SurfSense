"""
RBAC (Role-Based Access Control) utility functions.
Provides helpers for checking user permissions in search spaces.
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
    SearchSpace,
    SearchSpaceMembership,
    SearchSpaceRole,
    has_permission,
)


async def get_user_membership(
    session: AsyncSession,
    user_id: UUID,
    search_space_id: int,
) -> SearchSpaceMembership | None:
    """
    Get the user's membership in a search space.

    Args:
        session: Database session
        user_id: User UUID
        search_space_id: Search space ID

    Returns:
        SearchSpaceMembership if found, None otherwise
    """
    result = await session.execute(
        select(SearchSpaceMembership)
        .options(selectinload(SearchSpaceMembership.role))
        .filter(
            SearchSpaceMembership.user_id == user_id,
            SearchSpaceMembership.search_space_id == search_space_id,
        )
    )
    return result.scalars().first()


async def get_user_permissions(
    session: AsyncSession,
    user_id: UUID,
    search_space_id: int,
) -> list[str]:
    """
    Get the user's permissions in a search space.

    Args:
        session: Database session
        user_id: User UUID
        search_space_id: Search space ID

    Returns:
        List of permission strings
    """
    membership = await get_user_membership(session, user_id, search_space_id)

    if not membership:
        return []

    # Owners always have full access
    if membership.is_owner:
        return [Permission.FULL_ACCESS.value]

    # Get permissions from role
    if membership.role:
        return membership.role.permissions or []

    return []


async def _enforce_api_access_gate(
    session: AsyncSession,
    auth: AuthContext,
    search_space_id: int,
    search_space: SearchSpace | None = None,
) -> SearchSpace:
    if search_space is None:
        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

    if not search_space:
        raise HTTPException(status_code=404, detail="Search space not found")

    if auth.is_gated and not search_space.api_access_enabled:
        raise HTTPException(
            status_code=403,
            detail="API access is not enabled for this search space.",
        )

    return search_space


async def check_permission(
    session: AsyncSession,
    auth: AuthContext,
    search_space_id: int,
    required_permission: str,
    error_message: str = "You don't have permission to perform this action",
) -> SearchSpaceMembership:
    """
    Check if a user has a specific permission in a search space.
    Raises HTTPException if permission is denied.

    Args:
        session: Database session
        user: User object
        search_space_id: Search space ID
        required_permission: Permission string to check
        error_message: Custom error message for permission denied

    Returns:
        SearchSpaceMembership if permission granted

    Raises:
        HTTPException: If user doesn't have access or permission
    """
    membership = await get_user_membership(session, auth.user.id, search_space_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this search space",
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

    await _enforce_api_access_gate(session, auth, search_space_id)

    return membership


async def check_search_space_access(
    session: AsyncSession,
    auth: AuthContext,
    search_space_id: int,
) -> SearchSpaceMembership:
    """
    Check if a user has any access to a search space.
    This is used for basic access control (user is a member).

    Args:
        session: Database session
        user: User object
        search_space_id: Search space ID

    Returns:
        SearchSpaceMembership if user has access

    Raises:
        HTTPException: If user doesn't have access
    """
    membership = await get_user_membership(session, auth.user.id, search_space_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this search space",
        )

    await _enforce_api_access_gate(session, auth, search_space_id)

    return membership


async def is_search_space_owner(
    session: AsyncSession,
    user_id: UUID,
    search_space_id: int,
) -> bool:
    """
    Check if a user is the owner of a search space.

    Args:
        session: Database session
        user_id: User UUID
        search_space_id: Search space ID

    Returns:
        True if user is the owner, False otherwise
    """
    membership = await get_user_membership(session, user_id, search_space_id)
    return membership is not None and membership.is_owner


async def get_search_space_with_access_check(
    session: AsyncSession,
    auth: AuthContext,
    search_space_id: int,
    required_permission: str | None = None,
) -> tuple[SearchSpace, SearchSpaceMembership]:
    """
    Get a search space with access and optional permission check.

    Args:
        session: Database session
        user: User object
        search_space_id: Search space ID
        required_permission: Optional permission to check

    Returns:
        Tuple of (SearchSpace, SearchSpaceMembership)

    Raises:
        HTTPException: If search space not found or user lacks access/permission
    """
    # Get the search space
    result = await session.execute(
        select(SearchSpace).filter(SearchSpace.id == search_space_id)
    )
    search_space = result.scalars().first()

    if not search_space:
        raise HTTPException(status_code=404, detail="Search space not found")

    # Check access
    if required_permission:
        membership = await check_permission(
            session, auth, search_space_id, required_permission
        )
    else:
        membership = await check_search_space_access(session, auth, search_space_id)

    await _enforce_api_access_gate(session, auth, search_space_id, search_space)

    return search_space, membership


def generate_invite_code() -> str:
    """
    Generate a unique invite code for search space invites.

    Returns:
        A 32-character URL-safe invite code
    """
    return secrets.token_urlsafe(24)


async def get_default_role(
    session: AsyncSession,
    search_space_id: int,
) -> SearchSpaceRole | None:
    """
    Get the default role for a search space (used when accepting invites without a specific role).

    Args:
        session: Database session
        search_space_id: Search space ID

    Returns:
        Default SearchSpaceRole or None
    """
    result = await session.execute(
        select(SearchSpaceRole).filter(
            SearchSpaceRole.search_space_id == search_space_id,
            SearchSpaceRole.is_default == True,  # noqa: E712
        )
    )
    return result.scalars().first()


async def get_owner_role(
    session: AsyncSession,
    search_space_id: int,
) -> SearchSpaceRole | None:
    """
    Get the Owner role for a search space.

    Args:
        session: Database session
        search_space_id: Search space ID

    Returns:
        Owner SearchSpaceRole or None
    """
    result = await session.execute(
        select(SearchSpaceRole).filter(
            SearchSpaceRole.search_space_id == search_space_id,
            SearchSpaceRole.name == "Owner",
        )
    )
    return result.scalars().first()
