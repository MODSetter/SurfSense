from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    LLMConfig,
    SearchSpace,
    User,
    UserSearchSpacePreference,
    get_async_session,
)
from app.schemas import LLMConfigCreate, LLMConfigRead, LLMConfigUpdate
from app.services.llm_service import validate_llm_config
from app.users import current_active_user

router = APIRouter()


# Helper function to check search space access
async def check_search_space_access(
    session: AsyncSession, search_space_id: int, user: User
) -> SearchSpace:
    """Verify that the user has access to the search space"""
    result = await session.execute(
        select(SearchSpace).filter(
            SearchSpace.id == search_space_id, SearchSpace.user_id == user.id
        )
    )
    search_space = result.scalars().first()
    if not search_space:
        raise HTTPException(
            status_code=404,
            detail="Search space not found or you don't have permission to access it",
        )
    return search_space


# Helper function to get or create user search space preference
async def get_or_create_user_preference(
    session: AsyncSession, user_id, search_space_id: int
) -> UserSearchSpacePreference:
    """Get or create user preference for a search space"""
    result = await session.execute(
        select(UserSearchSpacePreference)
        .filter(
            UserSearchSpacePreference.user_id == user_id,
            UserSearchSpacePreference.search_space_id == search_space_id,
        )
        .options(
            selectinload(UserSearchSpacePreference.long_context_llm),
            selectinload(UserSearchSpacePreference.fast_llm),
            selectinload(UserSearchSpacePreference.strategic_llm),
        )
    )
    preference = result.scalars().first()

    if not preference:
        # Create new preference entry
        preference = UserSearchSpacePreference(
            user_id=user_id,
            search_space_id=search_space_id,
        )
        session.add(preference)
        await session.commit()
        await session.refresh(preference)

    return preference


class LLMPreferencesUpdate(BaseModel):
    """Schema for updating user LLM preferences"""

    long_context_llm_id: int | None = None
    fast_llm_id: int | None = None
    strategic_llm_id: int | None = None


class LLMPreferencesRead(BaseModel):
    """Schema for reading user LLM preferences"""

    long_context_llm_id: int | None = None
    fast_llm_id: int | None = None
    strategic_llm_id: int | None = None
    long_context_llm: LLMConfigRead | None = None
    fast_llm: LLMConfigRead | None = None
    strategic_llm: LLMConfigRead | None = None


@router.post("/llm-configs", response_model=LLMConfigRead)
async def create_llm_config(
    llm_config: LLMConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create a new LLM configuration for a search space"""
    try:
        # Verify user has access to the search space
        await check_search_space_access(session, llm_config.search_space_id, user)

        # Validate the LLM configuration by making a test API call
        is_valid, error_message = await validate_llm_config(
            provider=llm_config.provider.value,
            model_name=llm_config.model_name,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
            custom_provider=llm_config.custom_provider,
            litellm_params=llm_config.litellm_params,
        )

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid LLM configuration: {error_message}",
            )

        db_llm_config = LLMConfig(**llm_config.model_dump())
        session.add(db_llm_config)
        await session.commit()
        await session.refresh(db_llm_config)
        return db_llm_config
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create LLM configuration: {e!s}"
        ) from e


@router.get("/llm-configs", response_model=list[LLMConfigRead])
async def read_llm_configs(
    search_space_id: int,
    skip: int = 0,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get all LLM configurations for a search space"""
    try:
        # Verify user has access to the search space
        await check_search_space_access(session, search_space_id, user)

        result = await session.execute(
            select(LLMConfig)
            .filter(LLMConfig.search_space_id == search_space_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch LLM configurations: {e!s}"
        ) from e


@router.get("/llm-configs/{llm_config_id}", response_model=LLMConfigRead)
async def read_llm_config(
    llm_config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a specific LLM configuration by ID"""
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        llm_config = result.scalars().first()

        if not llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has access to the search space
        await check_search_space_access(session, llm_config.search_space_id, user)

        return llm_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch LLM configuration: {e!s}"
        ) from e


@router.put("/llm-configs/{llm_config_id}", response_model=LLMConfigRead)
async def update_llm_config(
    llm_config_id: int,
    llm_config_update: LLMConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Update an existing LLM configuration"""
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        db_llm_config = result.scalars().first()

        if not db_llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has access to the search space
        await check_search_space_access(session, db_llm_config.search_space_id, user)

        update_data = llm_config_update.model_dump(exclude_unset=True)

        # Apply updates to a temporary copy for validation
        temp_config = {
            "provider": update_data.get("provider", db_llm_config.provider.value),
            "model_name": update_data.get("model_name", db_llm_config.model_name),
            "api_key": update_data.get("api_key", db_llm_config.api_key),
            "api_base": update_data.get("api_base", db_llm_config.api_base),
            "custom_provider": update_data.get(
                "custom_provider", db_llm_config.custom_provider
            ),
            "litellm_params": update_data.get(
                "litellm_params", db_llm_config.litellm_params
            ),
        }

        # Validate the updated configuration
        is_valid, error_message = await validate_llm_config(
            provider=temp_config["provider"],
            model_name=temp_config["model_name"],
            api_key=temp_config["api_key"],
            api_base=temp_config["api_base"],
            custom_provider=temp_config["custom_provider"],
            litellm_params=temp_config["litellm_params"],
        )

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid LLM configuration: {error_message}",
            )

        # Apply updates to the database object
        for key, value in update_data.items():
            setattr(db_llm_config, key, value)

        await session.commit()
        await session.refresh(db_llm_config)
        return db_llm_config
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM configuration: {e!s}"
        ) from e


@router.delete("/llm-configs/{llm_config_id}", response_model=dict)
async def delete_llm_config(
    llm_config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete an LLM configuration"""
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        db_llm_config = result.scalars().first()

        if not db_llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has access to the search space
        await check_search_space_access(session, db_llm_config.search_space_id, user)

        await session.delete(db_llm_config)
        await session.commit()
        return {"message": "LLM configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete LLM configuration: {e!s}"
        ) from e


# User LLM Preferences endpoints


@router.get(
    "/search-spaces/{search_space_id}/llm-preferences",
    response_model=LLMPreferencesRead,
)
async def get_user_llm_preferences(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get the current user's LLM preferences for a specific search space"""
    try:
        # Verify user has access to the search space
        await check_search_space_access(session, search_space_id, user)

        # Get or create user preference for this search space
        preference = await get_or_create_user_preference(
            session, user.id, search_space_id
        )

        return {
            "long_context_llm_id": preference.long_context_llm_id,
            "fast_llm_id": preference.fast_llm_id,
            "strategic_llm_id": preference.strategic_llm_id,
            "long_context_llm": preference.long_context_llm,
            "fast_llm": preference.fast_llm,
            "strategic_llm": preference.strategic_llm,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch LLM preferences: {e!s}"
        ) from e


@router.put(
    "/search-spaces/{search_space_id}/llm-preferences",
    response_model=LLMPreferencesRead,
)
async def update_user_llm_preferences(
    search_space_id: int,
    preferences: LLMPreferencesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Update the current user's LLM preferences for a specific search space"""
    try:
        # Verify user has access to the search space
        await check_search_space_access(session, search_space_id, user)

        # Get or create user preference for this search space
        preference = await get_or_create_user_preference(
            session, user.id, search_space_id
        )

        # Validate that all provided LLM config IDs belong to the search space
        update_data = preferences.model_dump(exclude_unset=True)

        # Store language from configs to validate consistency
        languages = set()

        for _key, llm_config_id in update_data.items():
            if llm_config_id is not None:
                # Verify the LLM config belongs to the search space
                result = await session.execute(
                    select(LLMConfig).filter(
                        LLMConfig.id == llm_config_id,
                        LLMConfig.search_space_id == search_space_id,
                    )
                )
                llm_config = result.scalars().first()
                if not llm_config:
                    raise HTTPException(
                        status_code=404,
                        detail=f"LLM configuration {llm_config_id} not found in this search space",
                    )

                # Collect language for consistency check
                languages.add(llm_config.language)

        # Check if all selected LLM configs have the same language
        if len(languages) > 1:
            raise HTTPException(
                status_code=400,
                detail="All selected LLM configurations must have the same language setting",
            )

        # Update user preferences
        for key, value in update_data.items():
            setattr(preference, key, value)

        await session.commit()
        await session.refresh(preference)

        # Reload relationships
        await session.refresh(
            preference, ["long_context_llm", "fast_llm", "strategic_llm"]
        )

        # Return updated preferences
        return {
            "long_context_llm_id": preference.long_context_llm_id,
            "fast_llm_id": preference.fast_llm_id,
            "strategic_llm_id": preference.strategic_llm_id,
            "long_context_llm": preference.long_context_llm,
            "fast_llm": preference.fast_llm,
            "strategic_llm": preference.strategic_llm,
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM preferences: {e!s}"
        ) from e
