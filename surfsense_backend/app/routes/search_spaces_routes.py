import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import (
    NewLLMConfig,
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    SearchSpaceRole,
    User,
    get_async_session,
    get_default_roles_config,
)
from app.schemas import (
    LLMPreferencesRead,
    LLMPreferencesUpdate,
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
                .order_by(SearchSpace.id.asc())
                .offset(skip)
                .limit(limit)
            )
        else:
            # Return all search spaces the user has membership in
            result = await session.execute(
                select(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .order_by(SearchSpace.id.asc())
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


# =============================================================================
# LLM Preferences Routes
# =============================================================================


async def _get_llm_config_by_id(
    session: AsyncSession, config_id: int | None
) -> dict | None:
    """
    Get an LLM config by ID as a dictionary. Returns database config for positive IDs,
    global config for negative IDs, Auto mode config for ID 0, or None if ID is None.
    """
    if config_id is None:
        return None

    # Auto mode (ID 0) - uses LiteLLM Router for load balancing
    if config_id == 0:
        return {
            "id": 0,
            "name": "Auto (Load Balanced)",
            "description": "Automatically routes requests across available LLM providers for optimal performance and rate limit handling",
            "provider": "AUTO",
            "custom_provider": None,
            "model_name": "auto",
            "api_base": None,
            "litellm_params": {},
            "system_instructions": "",
            "use_default_system_instructions": True,
            "citations_enabled": True,
            "is_global": True,
            "is_auto_mode": True,
        }

    if config_id < 0:
        # Global config - find from YAML
        global_configs = config.GLOBAL_LLM_CONFIGS
        for cfg in global_configs:
            if cfg.get("id") == config_id:
                return {
                    "id": cfg.get("id"),
                    "name": cfg.get("name"),
                    "description": cfg.get("description"),
                    "provider": cfg.get("provider"),
                    "custom_provider": cfg.get("custom_provider"),
                    "model_name": cfg.get("model_name"),
                    "api_base": cfg.get("api_base"),
                    "litellm_params": cfg.get("litellm_params", {}),
                    "system_instructions": cfg.get("system_instructions", ""),
                    "use_default_system_instructions": cfg.get(
                        "use_default_system_instructions", True
                    ),
                    "citations_enabled": cfg.get("citations_enabled", True),
                    "is_global": True,
                }
        return None
    else:
        # Database config - convert to dict
        result = await session.execute(
            select(NewLLMConfig).filter(NewLLMConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if db_config:
            return {
                "id": db_config.id,
                "name": db_config.name,
                "description": db_config.description,
                "provider": db_config.provider.value if db_config.provider else None,
                "custom_provider": db_config.custom_provider,
                "model_name": db_config.model_name,
                "api_key": db_config.api_key,
                "api_base": db_config.api_base,
                "litellm_params": db_config.litellm_params or {},
                "system_instructions": db_config.system_instructions or "",
                "use_default_system_instructions": db_config.use_default_system_instructions,
                "citations_enabled": db_config.citations_enabled,
                "created_at": db_config.created_at.isoformat()
                if db_config.created_at
                else None,
                "search_space_id": db_config.search_space_id,
            }
        return None


@router.get(
    "/search-spaces/{search_space_id}/llm-preferences",
    response_model=LLMPreferencesRead,
)
async def get_llm_preferences(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get LLM preferences (role assignments) for a search space.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM preferences",
        )

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        # Get full config objects for each role
        agent_llm = await _get_llm_config_by_id(session, search_space.agent_llm_id)
        document_summary_llm = await _get_llm_config_by_id(
            session, search_space.document_summary_llm_id
        )

        return LLMPreferencesRead(
            agent_llm_id=search_space.agent_llm_id,
            document_summary_llm_id=search_space.document_summary_llm_id,
            agent_llm=agent_llm,
            document_summary_llm=document_summary_llm,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get LLM preferences")
        raise HTTPException(
            status_code=500, detail=f"Failed to get LLM preferences: {e!s}"
        ) from e


@router.put(
    "/search-spaces/{search_space_id}/llm-preferences",
    response_model=LLMPreferencesRead,
)
async def update_llm_preferences(
    search_space_id: int,
    preferences: LLMPreferencesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update LLM preferences (role assignments) for a search space.
    Requires LLM_CONFIGS_UPDATE permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_UPDATE.value,
            "You don't have permission to update LLM preferences",
        )

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        # Update preferences
        update_data = preferences.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(search_space, key, value)

        await session.commit()
        await session.refresh(search_space)

        # Get full config objects for response
        agent_llm = await _get_llm_config_by_id(session, search_space.agent_llm_id)
        document_summary_llm = await _get_llm_config_by_id(
            session, search_space.document_summary_llm_id
        )

        return LLMPreferencesRead(
            agent_llm_id=search_space.agent_llm_id,
            document_summary_llm_id=search_space.document_summary_llm_id,
            agent_llm=agent_llm,
            document_summary_llm=document_summary_llm,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to update LLM preferences")
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM preferences: {e!s}"
        ) from e


@router.get("/searchspaces/{search_space_id}/snapshots")
async def list_search_space_snapshots(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all public chat snapshots for a search space.

    Requires PUBLIC_SHARING_VIEW permission.
    """
    from app.schemas.new_chat import PublicChatSnapshotsBySpaceResponse
    from app.services.public_chat_service import list_snapshots_for_search_space

    snapshots = await list_snapshots_for_search_space(
        session=session,
        search_space_id=search_space_id,
        user=user,
    )
    return PublicChatSnapshotsBySpaceResponse(snapshots=snapshots)
