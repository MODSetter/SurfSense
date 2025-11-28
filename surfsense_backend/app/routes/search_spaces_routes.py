import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    SearchSpaceRole,
    User,
    get_async_session,
    get_default_roles_config,
)
from app.schemas import (
    SearchSpaceCreate,
    SearchSpaceRead,
    SearchSpaceUpdate,
    SearchSpaceWithStats,
)
from app.users import current_active_user
from app.utils.rbac import check_permission, check_search_space_access

logger = logging.getLogger(__name__)

router = APIRouter()


async def create_default_roles_and_membership(
    session: AsyncSession,
    search_space_id: int,
    owner_user_id,
) -> None:
    """
    Create default system roles for a search space and add the owner as a member.

    Args:
        session: Database session
        search_space_id: The ID of the newly created search space
        owner_user_id: The UUID of the user who created the search space
    """
    # Create default roles
    default_roles = get_default_roles_config()
    owner_role_id = None

    for role_config in default_roles:
        db_role = SearchSpaceRole(
            name=role_config["name"],
            description=role_config["description"],
            permissions=role_config["permissions"],
            is_default=role_config["is_default"],
            is_system_role=role_config["is_system_role"],
            search_space_id=search_space_id,
        )
        session.add(db_role)
        await session.flush()  # Get the ID

        if role_config["name"] == "Owner":
            owner_role_id = db_role.id

    # Create owner membership
    owner_membership = SearchSpaceMembership(
        user_id=owner_user_id,
        search_space_id=search_space_id,
        role_id=owner_role_id,
        is_owner=True,
    )
    session.add(owner_membership)


@router.post("/searchspaces", response_model=SearchSpaceRead)
async def create_search_space(
    search_space: SearchSpaceCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        search_space_data = search_space.model_dump()

        # citations_enabled defaults to True (handled by Pydantic schema)
        # qna_custom_instructions defaults to None/empty (handled by DB)

        db_search_space = SearchSpace(**search_space_data, user_id=user.id)
        session.add(db_search_space)
        await session.flush()  # Get the search space ID

        # Create default roles and owner membership
        await create_default_roles_and_membership(session, db_search_space.id, user.id)

        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create search space: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create search space: {e!s}"
        ) from e


@router.get("/searchspaces", response_model=list[SearchSpaceWithStats])
async def read_search_spaces(
    skip: int = 0,
    limit: int = 200,
    owned_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get all search spaces the user has access to, with member count and ownership info.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        owned_only: If True, only return search spaces owned by the user.
                   If False (default), return all search spaces the user has access to.
    """
    try:
        if owned_only:
            # Return only search spaces where user is the original creator (user_id)
            result = await session.execute(
                select(SearchSpace)
                .filter(SearchSpace.user_id == user.id)
                .offset(skip)
                .limit(limit)
            )
        else:
            # Return all search spaces the user has membership in
            result = await session.execute(
                select(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .offset(skip)
                .limit(limit)
            )

        search_spaces = result.scalars().all()

        # Get member counts and ownership info for each search space
        search_spaces_with_stats = []
        for space in search_spaces:
            # Get member count
            count_result = await session.execute(
                select(func.count(SearchSpaceMembership.id)).filter(
                    SearchSpaceMembership.search_space_id == space.id
                )
            )
            member_count = count_result.scalar() or 1

            # Check if current user is owner
            ownership_result = await session.execute(
                select(SearchSpaceMembership).filter(
                    SearchSpaceMembership.search_space_id == space.id,
                    SearchSpaceMembership.user_id == user.id,
                    SearchSpaceMembership.is_owner == True,  # noqa: E712
                )
            )
            is_owner = ownership_result.scalars().first() is not None

            search_spaces_with_stats.append(
                SearchSpaceWithStats(
                    id=space.id,
                    name=space.name,
                    description=space.description,
                    created_at=space.created_at,
                    user_id=space.user_id,
                    citations_enabled=space.citations_enabled,
                    qna_custom_instructions=space.qna_custom_instructions,
                    member_count=member_count,
                    is_owner=is_owner,
                )
            )

        return search_spaces_with_stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search spaces: {e!s}"
        ) from e


@router.get("/searchspaces/prompts/community")
async def get_community_prompts():
    """
    Get community-curated prompts for SearchSpace System Instructions.
    This endpoint does not require authentication as it serves public prompts.
    """
    try:
        # Get the path to the prompts YAML file
        prompts_file = (
            Path(__file__).parent.parent
            / "prompts"
            / "public_search_space_prompts.yaml"
        )

        if not prompts_file.exists():
            raise HTTPException(
                status_code=404, detail="Community prompts file not found"
            )

        with open(prompts_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data.get("prompts", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load community prompts: {e!s}"
        ) from e


@router.get("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def read_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific search space by ID.
    Requires SETTINGS_VIEW permission or membership.
    """
    try:
        # Check if user has access (is a member)
        await check_search_space_access(session, user, search_space_id)

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        return search_space

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search space: {e!s}"
        ) from e


@router.put("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def update_search_space(
    search_space_id: int,
    search_space_update: SearchSpaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a search space.
    Requires SETTINGS_UPDATE permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update this search space",
        )

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        db_search_space = result.scalars().first()

        if not db_search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        update_data = search_space_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_search_space, key, value)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update search space: {e!s}"
        ) from e


@router.delete("/searchspaces/{search_space_id}", response_model=dict)
async def delete_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a search space.
    Requires SETTINGS_DELETE permission (only owners have this by default).
    """
    try:
        # Check permission - only those with SETTINGS_DELETE can delete
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.SETTINGS_DELETE.value,
            "You don't have permission to delete this search space",
        )

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        db_search_space = result.scalars().first()

        if not db_search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        await session.delete(db_search_space)
        await session.commit()
        return {"message": "Search space deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete search space: {e!s}"
        ) from e
