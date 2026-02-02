"""
API routes for NewLLMConfig CRUD operations.

NewLLMConfig combines LLM model settings with prompt configuration:
- LLM provider, model, API key, etc.
- Configurable system instructions
- Citation toggle
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.new_chat.system_prompt import get_default_system_instructions
from app.config import config
from app.db import (
    NewLLMConfig,
    Permission,
    User,
    get_async_session,
)
from app.schemas import (
    DefaultSystemInstructionsResponse,
    GlobalNewLLMConfigRead,
    NewLLMConfigCreate,
    NewLLMConfigRead,
    NewLLMConfigUpdate,
)
from app.services.llm_service import validate_llm_config
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Global Configs Routes
# =============================================================================


@router.get("/global-new-llm-configs", response_model=list[GlobalNewLLMConfigRead])
async def get_global_new_llm_configs(
    user: User = Depends(current_active_user),
):
    """
    Get all available global NewLLMConfig configurations.
    These are pre-configured by the system administrator and available to all users.
    API keys are not exposed through this endpoint.

    Includes:
    - Auto mode (ID 0): Uses LiteLLM Router for automatic load balancing
    - Global configs (negative IDs): Individual pre-configured LLM providers
    """
    try:
        global_configs = config.GLOBAL_LLM_CONFIGS
        safe_configs = []

        # Only include Auto mode if there are actual global configs to route to
        # Auto mode requires at least one global config with valid API key
        if global_configs and len(global_configs) > 0:
            safe_configs.append(
                {
                    "id": 0,
                    "name": "Auto (Load Balanced)",
                    "description": "Automatically routes requests across available LLM providers for optimal performance and rate limit handling. Recommended for most users.",
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
            )

        # Add individual global configs
        for cfg in global_configs:
            safe_config = {
                "id": cfg.get("id"),
                "name": cfg.get("name"),
                "description": cfg.get("description"),
                "provider": cfg.get("provider"),
                "custom_provider": cfg.get("custom_provider"),
                "model_name": cfg.get("model_name"),
                "api_base": cfg.get("api_base") or None,
                "litellm_params": cfg.get("litellm_params", {}),
                # New prompt configuration fields
                "system_instructions": cfg.get("system_instructions", ""),
                "use_default_system_instructions": cfg.get(
                    "use_default_system_instructions", True
                ),
                "citations_enabled": cfg.get("citations_enabled", True),
                "is_global": True,
            }
            safe_configs.append(safe_config)

        return safe_configs
    except Exception as e:
        logger.exception("Failed to fetch global NewLLMConfigs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch global configurations: {e!s}"
        ) from e


# =============================================================================
# CRUD Routes
# =============================================================================


@router.post("/new-llm-configs", response_model=NewLLMConfigRead)
async def create_new_llm_config(
    config_data: NewLLMConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new NewLLMConfig for a search space.
    Requires LLM_CONFIGS_CREATE permission.
    """
    try:
        # Verify user has permission
        await check_permission(
            session,
            user,
            config_data.search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create LLM configurations in this search space",
        )

        # Validate the LLM configuration by making a test API call
        is_valid, error_message = await validate_llm_config(
            provider=config_data.provider.value,
            model_name=config_data.model_name,
            api_key=config_data.api_key,
            api_base=config_data.api_base,
            custom_provider=config_data.custom_provider,
            litellm_params=config_data.litellm_params,
        )

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid LLM configuration: {error_message}",
            )

        # Create the config
        db_config = NewLLMConfig(**config_data.model_dump())
        session.add(db_config)
        await session.commit()
        await session.refresh(db_config)

        return db_config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create NewLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to create configuration: {e!s}"
        ) from e


@router.get("/new-llm-configs", response_model=list[NewLLMConfigRead])
async def list_new_llm_configs(
    search_space_id: int,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get all NewLLMConfigs for a search space.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        # Verify user has permission
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM configurations in this search space",
        )

        result = await session.execute(
            select(NewLLMConfig)
            .filter(NewLLMConfig.search_space_id == search_space_id)
            .order_by(NewLLMConfig.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list NewLLMConfigs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configurations: {e!s}"
        ) from e


@router.get(
    "/new-llm-configs/default-system-instructions",
    response_model=DefaultSystemInstructionsResponse,
)
async def get_default_system_instructions_endpoint(
    user: User = Depends(current_active_user),
):
    """
    Get the default SURFSENSE_SYSTEM_INSTRUCTIONS template.
    Useful for pre-populating the UI when creating a new configuration.
    """
    return DefaultSystemInstructionsResponse(
        default_system_instructions=get_default_system_instructions()
    )


@router.get("/new-llm-configs/{config_id}", response_model=NewLLMConfigRead)
async def get_new_llm_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific NewLLMConfig by ID.
    Requires LLM_CONFIGS_READ permission.
    """
    try:
        result = await session.execute(
            select(NewLLMConfig).filter(NewLLMConfig.id == config_id)
        )
        config = result.scalars().first()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Verify user has permission
        await check_permission(
            session,
            user,
            config.search_space_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view LLM configurations in this search space",
        )

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get NewLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configuration: {e!s}"
        ) from e


@router.put("/new-llm-configs/{config_id}", response_model=NewLLMConfigRead)
async def update_new_llm_config(
    config_id: int,
    update_data: NewLLMConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update an existing NewLLMConfig.
    Requires LLM_CONFIGS_UPDATE permission.
    """
    try:
        result = await session.execute(
            select(NewLLMConfig).filter(NewLLMConfig.id == config_id)
        )
        config = result.scalars().first()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Verify user has permission
        await check_permission(
            session,
            user,
            config.search_space_id,
            Permission.LLM_CONFIGS_UPDATE.value,
            "You don't have permission to update LLM configurations in this search space",
        )

        update_dict = update_data.model_dump(exclude_unset=True)

        # If updating LLM settings, validate them
        if any(
            key in update_dict
            for key in [
                "provider",
                "model_name",
                "api_key",
                "api_base",
                "custom_provider",
                "litellm_params",
            ]
        ):
            # Build the validation config from existing + updates
            validation_config = {
                "provider": update_dict.get("provider", config.provider).value
                if hasattr(update_dict.get("provider", config.provider), "value")
                else update_dict.get("provider", config.provider.value),
                "model_name": update_dict.get("model_name", config.model_name),
                "api_key": update_dict.get("api_key", config.api_key),
                "api_base": update_dict.get("api_base", config.api_base),
                "custom_provider": update_dict.get(
                    "custom_provider", config.custom_provider
                ),
                "litellm_params": update_dict.get(
                    "litellm_params", config.litellm_params
                ),
            }

            is_valid, error_message = await validate_llm_config(
                provider=validation_config["provider"],
                model_name=validation_config["model_name"],
                api_key=validation_config["api_key"],
                api_base=validation_config["api_base"],
                custom_provider=validation_config["custom_provider"],
                litellm_params=validation_config["litellm_params"],
            )

            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid LLM configuration: {error_message}",
                )

        # Apply updates
        for key, value in update_dict.items():
            setattr(config, key, value)

        await session.commit()
        await session.refresh(config)

        return config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to update NewLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to update configuration: {e!s}"
        ) from e


@router.delete("/new-llm-configs/{config_id}", response_model=dict)
async def delete_new_llm_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a NewLLMConfig.
    Requires LLM_CONFIGS_DELETE permission.
    """
    try:
        result = await session.execute(
            select(NewLLMConfig).filter(NewLLMConfig.id == config_id)
        )
        config = result.scalars().first()

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Verify user has permission
        await check_permission(
            session,
            user,
            config.search_space_id,
            Permission.LLM_CONFIGS_DELETE.value,
            "You don't have permission to delete LLM configurations in this search space",
        )

        await session.delete(config)
        await session.commit()

        return {"message": "Configuration deleted successfully", "id": config_id}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to delete NewLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete configuration: {e!s}"
        ) from e
