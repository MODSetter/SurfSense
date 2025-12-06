import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import (
    LLMConfig,
    Permission,
    SearchSpace,
    User,
    get_async_session,
)
from app.schemas import LLMConfigCreate, LLMConfigRead, LLMConfigUpdate
from app.services.llm_service import validate_llm_config
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


class LLMPreferencesUpdate(BaseModel):
    """Schema for updating search space LLM preferences"""

    long_context_llm_id: int | None = None
    fast_llm_id: int | None = None
    strategic_llm_id: int | None = None


class LLMPreferencesRead(BaseModel):
    """Schema for reading search space LLM preferences"""

    long_context_llm_id: int | None = None
    fast_llm_id: int | None = None
    strategic_llm_id: int | None = None
    long_context_llm: LLMConfigRead | None = None
    fast_llm: LLMConfigRead | None = None
    strategic_llm: LLMConfigRead | None = None


class GlobalLLMConfigRead(BaseModel):
    """Schema for reading global LLM configs (without API key)"""

    id: int
    name: str
    provider: str
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    language: str | None = None
    litellm_params: dict | None = None
    is_global: bool = True


# Global LLM Config endpoints


@router.get("/global-llm-configs", response_model=list[GlobalLLMConfigRead])
async def get_global_llm_configs(
    user: User = Depends(current_active_user),
):
    """
    Get all available global LLM configurations.
    These are pre-configured by the system administrator and available to all users.
    API keys are not exposed through this endpoint.
    """
    try:
        global_configs = config.GLOBAL_LLM_CONFIGS

        # Remove API keys from response
        safe_configs = []
        for cfg in global_configs:
            safe_config = {
                "id": cfg.get("id"),
                "name": cfg.get("name"),
                "provider": cfg.get("provider"),
                "custom_provider": cfg.get("custom_provider"),
                "model_name": cfg.get("model_name"),
                "api_base": cfg.get("api_base"),
                "language": cfg.get("language"),
                "litellm_params": cfg.get("litellm_params", {}),
                "is_global": True,
            }
            safe_configs.append(safe_config)

        return safe_configs
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch global LLM configs: {e!s}"
        ) from e


@router.post("/llm-configs", response_model=LLMConfigRead)
async def create_llm_config(
    llm_config: LLMConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new LLM configuration for a search space.
    Requires LLM_CONFIGS_CREATE permission.
    """
    try:
        # Verify user has permission to create LLM configs
        await check_permission(
            session,
            user,
            llm_config.search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create LLM configurations in this search space",
        )

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
    """
    Get all LLM configurations for a search space.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        # Verify user has permission to read LLM configs
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM configurations in this search space",
        )

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
    """
    Get a specific LLM configuration by ID.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        llm_config = result.scalars().first()

        if not llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has permission to read LLM configs
        await check_permission(
            session,
            user,
            llm_config.search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM configurations in this search space",
        )

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
    """
    Update an existing LLM configuration.
    Requires LLM_CONFIGS_UPDATE permission.
    """
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        db_llm_config = result.scalars().first()

        if not db_llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has permission to update LLM configs
        await check_permission(
            session,
            user,
            db_llm_config.search_space_id,
            Permission.LLM_CONFIGS_UPDATE.value,
            "You don't have permission to update LLM configurations in this search space",
        )

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
    """
    Delete an LLM configuration.
    Requires LLM_CONFIGS_DELETE permission.
    """
    try:
        # Get the LLM config
        result = await session.execute(
            select(LLMConfig).filter(LLMConfig.id == llm_config_id)
        )
        db_llm_config = result.scalars().first()

        if not db_llm_config:
            raise HTTPException(status_code=404, detail="LLM configuration not found")

        # Verify user has permission to delete LLM configs
        await check_permission(
            session,
            user,
            db_llm_config.search_space_id,
            Permission.LLM_CONFIGS_DELETE.value,
            "You don't have permission to delete LLM configurations in this search space",
        )

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


# Search Space LLM Preferences endpoints


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
    Get the LLM preferences for a specific search space.
    LLM preferences are shared by all members of the search space.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        # Verify user has permission to read LLM configs
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM preferences in this search space",
        )

        # Get the search space
        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        # Helper function to get config (global or custom)
        async def get_config_for_id(config_id):
            if config_id is None:
                return None

            # Check if it's a global config (negative ID)
            if config_id < 0:
                for cfg in config.GLOBAL_LLM_CONFIGS:
                    if cfg.get("id") == config_id:
                        # Return as LLMConfigRead-compatible dict
                        return {
                            "id": cfg.get("id"),
                            "name": cfg.get("name"),
                            "provider": cfg.get("provider"),
                            "custom_provider": cfg.get("custom_provider"),
                            "model_name": cfg.get("model_name"),
                            "api_key": "***GLOBAL***",  # Don't expose the actual key
                            "api_base": cfg.get("api_base"),
                            "language": cfg.get("language"),
                            "litellm_params": cfg.get("litellm_params"),
                            "created_at": None,
                            "search_space_id": search_space_id,
                        }
                return None

            # It's a custom config, fetch from database
            result = await session.execute(
                select(LLMConfig).filter(LLMConfig.id == config_id)
            )
            return result.scalars().first()

        # Get the configs (from DB for custom, or constructed for global)
        long_context_llm = await get_config_for_id(search_space.long_context_llm_id)
        fast_llm = await get_config_for_id(search_space.fast_llm_id)
        strategic_llm = await get_config_for_id(search_space.strategic_llm_id)

        return {
            "long_context_llm_id": search_space.long_context_llm_id,
            "fast_llm_id": search_space.fast_llm_id,
            "strategic_llm_id": search_space.strategic_llm_id,
            "long_context_llm": long_context_llm,
            "fast_llm": fast_llm,
            "strategic_llm": strategic_llm,
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
async def update_llm_preferences(
    search_space_id: int,
    preferences: LLMPreferencesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update the LLM preferences for a specific search space.
    LLM preferences are shared by all members of the search space.
    Requires SETTINGS_UPDATE permission (only users with settings access can change).
    """
    try:
        # Verify user has permission to update settings (not just LLM configs)
        # This ensures only users with settings access can change shared LLM preferences
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update LLM preferences in this search space",
        )

        # Get the search space
        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == search_space_id)
        )
        search_space = result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        # Validate that all provided LLM config IDs belong to the search space
        update_data = preferences.model_dump(exclude_unset=True)

        # Store language from configs to validate consistency
        languages = set()

        for _key, llm_config_id in update_data.items():
            if llm_config_id is not None:
                # Check if this is a global config (negative ID)
                if llm_config_id < 0:
                    # Validate global config exists
                    global_config = None
                    for cfg in config.GLOBAL_LLM_CONFIGS:
                        if cfg.get("id") == llm_config_id:
                            global_config = cfg
                            break

                    if not global_config:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Global LLM configuration {llm_config_id} not found",
                        )

                    # Collect language for consistency check (if explicitly set)
                    lang = global_config.get("language")
                    if lang and lang.strip():  # Only add non-empty languages
                        languages.add(lang.strip())
                else:
                    # Verify the LLM config belongs to the search space (custom config)
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

                    # Collect language for consistency check (if explicitly set)
                    if llm_config.language and llm_config.language.strip():
                        languages.add(llm_config.language.strip())

        # Language consistency check - only warn if there are multiple explicit languages
        # Allow mixing configs with and without language settings
        if len(languages) > 1:
            # Log warning but allow the operation
            logger.warning(
                f"Multiple languages detected in LLM selection for search_space {search_space_id}: {languages}. "
                "This may affect response quality."
            )

        # Update search space LLM preferences
        for key, value in update_data.items():
            setattr(search_space, key, value)

        await session.commit()
        await session.refresh(search_space)

        # Helper function to get config (global or custom)
        async def get_config_for_id(config_id):
            if config_id is None:
                return None

            # Check if it's a global config (negative ID)
            if config_id < 0:
                for cfg in config.GLOBAL_LLM_CONFIGS:
                    if cfg.get("id") == config_id:
                        # Return as LLMConfigRead-compatible dict
                        return {
                            "id": cfg.get("id"),
                            "name": cfg.get("name"),
                            "provider": cfg.get("provider"),
                            "custom_provider": cfg.get("custom_provider"),
                            "model_name": cfg.get("model_name"),
                            "api_key": "***GLOBAL***",  # Don't expose the actual key
                            "api_base": cfg.get("api_base"),
                            "language": cfg.get("language"),
                            "litellm_params": cfg.get("litellm_params"),
                            "created_at": None,
                            "search_space_id": search_space_id,
                        }
                return None

            # It's a custom config, fetch from database
            result = await session.execute(
                select(LLMConfig).filter(LLMConfig.id == config_id)
            )
            return result.scalars().first()

        # Get the configs (from DB for custom, or constructed for global)
        long_context_llm = await get_config_for_id(search_space.long_context_llm_id)
        fast_llm = await get_config_for_id(search_space.fast_llm_id)
        strategic_llm = await get_config_for_id(search_space.strategic_llm_id)

        # Return updated preferences
        return {
            "long_context_llm_id": search_space.long_context_llm_id,
            "fast_llm_id": search_space.fast_llm_id,
            "strategic_llm_id": search_space.strategic_llm_id,
            "long_context_llm": long_context_llm,
            "fast_llm": fast_llm,
            "strategic_llm": strategic_llm,
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update LLM preferences: {e!s}"
        ) from e
