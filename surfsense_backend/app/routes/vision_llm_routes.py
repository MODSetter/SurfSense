import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Permission,
    User,
    VisionLLMConfig,
    get_async_session,
)
from app.schemas import (
    GlobalVisionLLMConfigRead,
    VisionLLMConfigCreate,
    VisionLLMConfigRead,
    VisionLLMConfigUpdate,
)
from app.services.vision_model_list_service import get_vision_model_list
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Vision Model Catalogue (from OpenRouter, filtered for image-input models)
# =============================================================================


class VisionModelListItem(BaseModel):
    value: str
    label: str
    provider: str
    context_window: str | None = None


@router.get("/vision-models", response_model=list[VisionModelListItem])
async def list_vision_models(
    user: User = Depends(current_active_user),
):
    """Return vision-capable models sourced from OpenRouter (filtered by image input)."""
    try:
        return await get_vision_model_list()
    except Exception as e:
        logger.exception("Failed to fetch vision model list")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch vision model list: {e!s}"
        ) from e


# =============================================================================
# Global Vision LLM Configs (from YAML)
# =============================================================================


@router.get(
    "/global-vision-llm-configs",
    response_model=list[GlobalVisionLLMConfigRead],
)
async def get_global_vision_llm_configs(
    user: User = Depends(current_active_user),
):
    try:
        global_configs = config.GLOBAL_VISION_LLM_CONFIGS
        safe_configs = []

        if global_configs and len(global_configs) > 0:
            safe_configs.append(
                {
                    "id": 0,
                    "name": "Auto (Fastest)",
                    "description": "Automatically routes across available vision LLM providers.",
                    "provider": "AUTO",
                    "custom_provider": None,
                    "model_name": "auto",
                    "api_base": None,
                    "api_version": None,
                    "litellm_params": {},
                    "is_global": True,
                    "is_auto_mode": True,
                }
            )

        for cfg in global_configs:
            safe_configs.append(
                {
                    "id": cfg.get("id"),
                    "name": cfg.get("name"),
                    "description": cfg.get("description"),
                    "provider": cfg.get("provider"),
                    "custom_provider": cfg.get("custom_provider"),
                    "model_name": cfg.get("model_name"),
                    "api_base": cfg.get("api_base") or None,
                    "api_version": cfg.get("api_version") or None,
                    "litellm_params": cfg.get("litellm_params", {}),
                    "is_global": True,
                }
            )

        return safe_configs
    except Exception as e:
        logger.exception("Failed to fetch global vision LLM configs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configs: {e!s}"
        ) from e


# =============================================================================
# VisionLLMConfig CRUD
# =============================================================================


@router.post("/vision-llm-configs", response_model=VisionLLMConfigRead)
async def create_vision_llm_config(
    config_data: VisionLLMConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_permission(
            session,
            user,
            config_data.search_space_id,
            Permission.VISION_CONFIGS_CREATE.value,
            "You don't have permission to create vision LLM configs in this search space",
        )

        db_config = VisionLLMConfig(**config_data.model_dump(), user_id=user.id)
        session.add(db_config)
        await session.commit()
        await session.refresh(db_config)
        return db_config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create VisionLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to create config: {e!s}"
        ) from e


@router.get("/vision-llm-configs", response_model=list[VisionLLMConfigRead])
async def list_vision_llm_configs(
    search_space_id: int,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.VISION_CONFIGS_READ.value,
            "You don't have permission to view vision LLM configs in this search space",
        )

        result = await session.execute(
            select(VisionLLMConfig)
            .filter(VisionLLMConfig.search_space_id == search_space_id)
            .order_by(VisionLLMConfig.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list VisionLLMConfigs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configs: {e!s}"
        ) from e


@router.get(
    "/vision-llm-configs/{config_id}", response_model=VisionLLMConfigRead
)
async def get_vision_llm_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(VisionLLMConfig).filter(VisionLLMConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.VISION_CONFIGS_READ.value,
            "You don't have permission to view vision LLM configs in this search space",
        )
        return db_config

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get VisionLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch config: {e!s}"
        ) from e


@router.put(
    "/vision-llm-configs/{config_id}", response_model=VisionLLMConfigRead
)
async def update_vision_llm_config(
    config_id: int,
    update_data: VisionLLMConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(VisionLLMConfig).filter(VisionLLMConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.VISION_CONFIGS_CREATE.value,
            "You don't have permission to update vision LLM configs in this search space",
        )

        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(db_config, key, value)

        await session.commit()
        await session.refresh(db_config)
        return db_config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to update VisionLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {e!s}"
        ) from e


@router.delete("/vision-llm-configs/{config_id}", response_model=dict)
async def delete_vision_llm_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(VisionLLMConfig).filter(VisionLLMConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.VISION_CONFIGS_DELETE.value,
            "You don't have permission to delete vision LLM configs in this search space",
        )

        await session.delete(db_config)
        await session.commit()
        return {
            "message": "Vision LLM config deleted successfully",
            "id": config_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to delete VisionLLMConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete config: {e!s}"
        ) from e
