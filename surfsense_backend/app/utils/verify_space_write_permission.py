"""
Utility module for verifying write permissions on search spaces.

CRITICAL SECURITY: This module enforces that public spaces are read-only for non-owners.
"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User


async def verify_space_write_permission(
    session: AsyncSession,
    search_space_id: int,
    current_user: User,
) -> SearchSpace:
    """
    Verify that a user has write permission for a search space.

    Write access is granted if:
    - User owns the space, OR
    - User is a superuser

    Public spaces are READ-ONLY for non-owners (except superusers).
    Private spaces are completely inaccessible to non-owners (except superusers).

    Args:
        session: Database session
        search_space_id: ID of the search space
        current_user: Current authenticated user

    Returns:
        SearchSpace: The search space object if user has write permission

    Raises:
        HTTPException 404: If search space not found
        HTTPException 403: If user lacks write permission
    """
    # Get the search space
    space = await session.get(SearchSpace, search_space_id)

    if not space:
        raise HTTPException(
            status_code=404,
            detail="Search space not found"
        )

    # Owner always has write access
    if space.user_id == current_user.id:
        return space

    # Superusers have write access to all spaces
    if current_user.is_superuser:
        return space

    # Public spaces are read-only for non-owners
    if space.is_public:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify public space - read-only access for non-owners"
        )

    # Private spaces are not accessible at all to non-owners
    raise HTTPException(
        status_code=403,
        detail="Access denied to private space"
    )
