"""
API routes for NewLLMConfig CRUD operations.

NewLLMConfig combines model settings with prompt configuration:
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
from app.services.provider_capabilities import derive_supports_image_input
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_byok_config(config: NewLLMConfig) -> NewLLMConfigRead:
    """Augment a BYOK chat config row with the derived ``supports_image_input``.

    There is no DB column for ``supports_image_input`` — the value is
    resolved at the API boundary from LiteLLM's authoritative model map
    (default-allow on unknown). Returning ``NewLLMConfigRead`` here keeps
    the response shape consistent across list / detail / create / update
    endpoints without having to remember to set the field at every call
    site.
    """
    provider_value = (
        config.provider.value
        if hasattr(config.provider, "value")
        else str(config.provider)
    )
    litellm_params = config.litellm_params or {}
    base_model = (
        litellm_params.get("base_model") if isinstance(litellm_params, dict) else None
    )
    supports_image_input = derive_supports_image_input(
        provider=provider_value,
        model_name=config.model_name,
        base_model=base_model,
        custom_provider=config.custom_provider,
    )
    # ``model_validate`` runs the Pydantic conversion using the ORM
    # attribute access path enabled by ``ConfigDict(from_attributes=True)``,
    # then we layer the derived field on. ``model_copy(update=...)`` keeps
    # the surface immutable from the caller's perspective.
    base_read = NewLLMConfigRead.model_validate(config)
    return base_read.model_copy(update={"supports_image_input": supports_image_input})


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
                    "name": "Auto (Fastest)",
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
                    "billing_tier": "free",
                    "is_premium": False,
                    "anonymous_enabled": False,
                    "seo_enabled": False,
                    "seo_slug": None,
                    "seo_title": None,
                    "seo_description": None,
                    "quota_reserve_tokens": None,
                    # Auto routes across the configured pool, which usually
                    # includes at least one vision-capable deployment, so
                    # treat Auto as image-capable. The router itself will
                    # still pick a vision-capable deployment for messages
                    # carrying image_url blocks (LiteLLM Router falls back
                    # on ``404`` per its ``allowed_fails`` policy).
                    "supports_image_input": True,
                }
            )

        # Add individual global configs
        for cfg in global_configs:
            # Capability resolution: explicit value (YAML override or OR
            # `_supports_image_input(model)` payload baked in by the
            # OpenRouter integration service) wins. Fall back to the
            # LiteLLM-driven helper which default-allows on unknown so
            # we don't hide vision-capable models that happen to lack a
            # YAML annotation. The streaming task safety net is the
            # only place a False ever blocks.
            if "supports_image_input" in cfg:
                supports_image_input = bool(cfg.get("supports_image_input"))
            else:
                cfg_litellm_params = cfg.get("litellm_params") or {}
                cfg_base_model = (
                    cfg_litellm_params.get("base_model")
                    if isinstance(cfg_litellm_params, dict)
                    else None
                )
                supports_image_input = derive_supports_image_input(
                    provider=cfg.get("provider"),
                    model_name=cfg.get("model_name"),
                    base_model=cfg_base_model,
                    custom_provider=cfg.get("custom_provider"),
                )

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
                "billing_tier": cfg.get("billing_tier", "free"),
                "is_premium": cfg.get("billing_tier", "free") == "premium",
                "anonymous_enabled": cfg.get("anonymous_enabled", False),
                "seo_enabled": cfg.get("seo_enabled", False),
                "seo_slug": cfg.get("seo_slug"),
                "seo_title": cfg.get("seo_title"),
                "seo_description": cfg.get("seo_description"),
                "quota_reserve_tokens": cfg.get("quota_reserve_tokens"),
                "supports_image_input": supports_image_input,
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

        # Create the config with user association
        db_config = NewLLMConfig(**config_data.model_dump(), user_id=user.id)
        session.add(db_config)
        await session.commit()
        await session.refresh(db_config)

        return _serialize_byok_config(db_config)

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

        return [_serialize_byok_config(cfg) for cfg in result.scalars().all()]

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

        return _serialize_byok_config(config)

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

        return _serialize_byok_config(config)

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
