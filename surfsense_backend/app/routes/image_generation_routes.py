"""
Image Generation routes:
- CRUD for ImageGenerationConfig (user-created image model configs)
- Global image gen configs endpoint (from YAML)
- Image generation execution (calls litellm.aimage_generation())
- CRUD for ImageGeneration records (results)
- Image serving endpoint (serves b64_json images from DB, protected by signed tokens)
"""

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from litellm import aimage_generation
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    ImageGeneration,
    ImageGenerationConfig,
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import (
    GlobalImageGenConfigRead,
    ImageGenerationConfigCreate,
    ImageGenerationConfigRead,
    ImageGenerationConfigUpdate,
    ImageGenerationCreate,
    ImageGenerationListRead,
    ImageGenerationRead,
)
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    ImageGenRouterService,
    is_image_gen_auto_mode,
)
from app.users import current_active_user
from app.utils.rbac import check_permission
from app.utils.signed_image_urls import verify_image_token

router = APIRouter()
logger = logging.getLogger(__name__)

# Provider mapping for building litellm model strings.
# Only includes providers that support image generation.
# See: https://docs.litellm.ai/docs/image_generation#supported-providers
_PROVIDER_MAP = {
    "OPENAI": "openai",
    "AZURE_OPENAI": "azure",
    "GOOGLE": "gemini",  # Google AI Studio
    "VERTEX_AI": "vertex_ai",
    "BEDROCK": "bedrock",  # AWS Bedrock
    "RECRAFT": "recraft",
    "OPENROUTER": "openrouter",
    "XINFERENCE": "xinference",
    "NSCALE": "nscale",
}


def _get_global_image_gen_config(config_id: int) -> dict | None:
    """Get a global image generation configuration by ID (negative IDs)."""
    if config_id == IMAGE_GEN_AUTO_MODE_ID:
        return {
            "id": IMAGE_GEN_AUTO_MODE_ID,
            "name": "Auto (Load Balanced)",
            "provider": "AUTO",
            "model_name": "auto",
            "is_auto_mode": True,
        }
    if config_id > 0:
        return None
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if cfg.get("id") == config_id:
            return cfg
    return None


def _build_model_string(
    provider: str, model_name: str, custom_provider: str | None
) -> str:
    """Build a litellm model string from provider + model_name."""
    if custom_provider:
        return f"{custom_provider}/{model_name}"
    prefix = _PROVIDER_MAP.get(provider.upper(), provider.lower())
    return f"{prefix}/{model_name}"


async def _execute_image_generation(
    session: AsyncSession,
    image_gen: ImageGeneration,
    search_space: SearchSpace,
) -> None:
    """
    Call litellm.aimage_generation() with the appropriate config.

    Resolution order:
    1. Explicit image_generation_config_id on the request
    2. Search space's image_generation_config_id preference
    3. Falls back to Auto mode if available
    """
    config_id = image_gen.image_generation_config_id
    if config_id is None:
        config_id = search_space.image_generation_config_id or IMAGE_GEN_AUTO_MODE_ID
        image_gen.image_generation_config_id = config_id

    # Build kwargs
    gen_kwargs = {}
    if image_gen.n is not None:
        gen_kwargs["n"] = image_gen.n
    if image_gen.quality is not None:
        gen_kwargs["quality"] = image_gen.quality
    if image_gen.size is not None:
        gen_kwargs["size"] = image_gen.size
    if image_gen.style is not None:
        gen_kwargs["style"] = image_gen.style
    if image_gen.response_format is not None:
        gen_kwargs["response_format"] = image_gen.response_format

    if is_image_gen_auto_mode(config_id):
        if not ImageGenRouterService.is_initialized():
            raise ValueError(
                "Auto mode requested but Image Generation Router not initialized. "
                "Ensure global_llm_config.yaml has global_image_generation_configs."
            )
        response = await ImageGenRouterService.aimage_generation(
            prompt=image_gen.prompt, model="auto", **gen_kwargs
        )
    elif config_id < 0:
        # Global config from YAML
        cfg = _get_global_image_gen_config(config_id)
        if not cfg:
            raise ValueError(f"Global image generation config {config_id} not found")

        model_string = _build_model_string(
            cfg.get("provider", ""), cfg["model_name"], cfg.get("custom_provider")
        )
        gen_kwargs["api_key"] = cfg.get("api_key")
        if cfg.get("api_base"):
            gen_kwargs["api_base"] = cfg["api_base"]
        if cfg.get("api_version"):
            gen_kwargs["api_version"] = cfg["api_version"]
        if cfg.get("litellm_params"):
            gen_kwargs.update(cfg["litellm_params"])

        # User model override
        if image_gen.model:
            model_string = image_gen.model

        response = await aimage_generation(
            prompt=image_gen.prompt, model=model_string, **gen_kwargs
        )
    else:
        # Positive ID = DB ImageGenerationConfig
        result = await session.execute(
            select(ImageGenerationConfig).filter(ImageGenerationConfig.id == config_id)
        )
        db_cfg = result.scalars().first()
        if not db_cfg:
            raise ValueError(f"Image generation config {config_id} not found")

        model_string = _build_model_string(
            db_cfg.provider.value, db_cfg.model_name, db_cfg.custom_provider
        )
        gen_kwargs["api_key"] = db_cfg.api_key
        if db_cfg.api_base:
            gen_kwargs["api_base"] = db_cfg.api_base
        if db_cfg.api_version:
            gen_kwargs["api_version"] = db_cfg.api_version
        if db_cfg.litellm_params:
            gen_kwargs.update(db_cfg.litellm_params)

        # User model override
        if image_gen.model:
            model_string = image_gen.model

        response = await aimage_generation(
            prompt=image_gen.prompt, model=model_string, **gen_kwargs
        )

    # Store response
    image_gen.response_data = (
        response.model_dump() if hasattr(response, "model_dump") else dict(response)
    )
    if not image_gen.model and hasattr(response, "_hidden_params"):
        hidden = response._hidden_params
        if isinstance(hidden, dict) and hidden.get("model"):
            image_gen.model = hidden["model"]


# =============================================================================
# Global Image Generation Configs (from YAML)
# =============================================================================


@router.get(
    "/global-image-generation-configs",
    response_model=list[GlobalImageGenConfigRead],
)
async def get_global_image_gen_configs(
    user: User = Depends(current_active_user),
):
    """Get all global image generation configs. API keys are hidden."""
    try:
        global_configs = config.GLOBAL_IMAGE_GEN_CONFIGS
        safe_configs = []

        if global_configs and len(global_configs) > 0:
            safe_configs.append(
                {
                    "id": 0,
                    "name": "Auto (Load Balanced)",
                    "description": "Automatically routes across available image generation providers.",
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
        logger.exception("Failed to fetch global image generation configs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configs: {e!s}"
        ) from e


# =============================================================================
# ImageGenerationConfig CRUD
# =============================================================================


@router.post("/image-generation-configs", response_model=ImageGenerationConfigRead)
async def create_image_gen_config(
    config_data: ImageGenerationConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create a new image generation config for a search space."""
    try:
        await check_permission(
            session,
            user,
            config_data.search_space_id,
            Permission.IMAGE_GENERATIONS_CREATE.value,
            "You don't have permission to create image generation configs in this search space",
        )

        db_config = ImageGenerationConfig(**config_data.model_dump())
        session.add(db_config)
        await session.commit()
        await session.refresh(db_config)
        return db_config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create ImageGenerationConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to create config: {e!s}"
        ) from e


@router.get("/image-generation-configs", response_model=list[ImageGenerationConfigRead])
async def list_image_gen_configs(
    search_space_id: int,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List image generation configs for a search space."""
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.IMAGE_GENERATIONS_READ.value,
            "You don't have permission to view image generation configs in this search space",
        )

        result = await session.execute(
            select(ImageGenerationConfig)
            .filter(ImageGenerationConfig.search_space_id == search_space_id)
            .order_by(ImageGenerationConfig.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list ImageGenerationConfigs")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch configs: {e!s}"
        ) from e


@router.get(
    "/image-generation-configs/{config_id}", response_model=ImageGenerationConfigRead
)
async def get_image_gen_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a specific image generation config by ID."""
    try:
        result = await session.execute(
            select(ImageGenerationConfig).filter(ImageGenerationConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.IMAGE_GENERATIONS_READ.value,
            "You don't have permission to view image generation configs in this search space",
        )
        return db_config

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get ImageGenerationConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch config: {e!s}"
        ) from e


@router.put(
    "/image-generation-configs/{config_id}", response_model=ImageGenerationConfigRead
)
async def update_image_gen_config(
    config_id: int,
    update_data: ImageGenerationConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Update an existing image generation config."""
    try:
        result = await session.execute(
            select(ImageGenerationConfig).filter(ImageGenerationConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.IMAGE_GENERATIONS_CREATE.value,
            "You don't have permission to update image generation configs in this search space",
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
        logger.exception("Failed to update ImageGenerationConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {e!s}"
        ) from e


@router.delete("/image-generation-configs/{config_id}", response_model=dict)
async def delete_image_gen_config(
    config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete an image generation config."""
    try:
        result = await session.execute(
            select(ImageGenerationConfig).filter(ImageGenerationConfig.id == config_id)
        )
        db_config = result.scalars().first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        await check_permission(
            session,
            user,
            db_config.search_space_id,
            Permission.IMAGE_GENERATIONS_DELETE.value,
            "You don't have permission to delete image generation configs in this search space",
        )

        await session.delete(db_config)
        await session.commit()
        return {
            "message": "Image generation config deleted successfully",
            "id": config_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to delete ImageGenerationConfig")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete config: {e!s}"
        ) from e


# =============================================================================
# Image Generation Execution + Results CRUD
# =============================================================================


@router.post("/image-generations", response_model=ImageGenerationRead)
async def create_image_generation(
    data: ImageGenerationCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create and execute an image generation request."""
    try:
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.IMAGE_GENERATIONS_CREATE.value,
            "You don't have permission to create image generations in this search space",
        )

        result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == data.search_space_id)
        )
        search_space = result.scalars().first()
        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        db_image_gen = ImageGeneration(
            prompt=data.prompt,
            model=data.model,
            n=data.n,
            quality=data.quality,
            size=data.size,
            style=data.style,
            response_format=data.response_format,
            image_generation_config_id=data.image_generation_config_id,
            search_space_id=data.search_space_id,
            created_by_id=user.id,
        )
        session.add(db_image_gen)
        await session.flush()

        try:
            await _execute_image_generation(session, db_image_gen, search_space)
        except Exception as e:
            logger.exception("Image generation call failed")
            db_image_gen.error_message = str(e)

        await session.commit()
        await session.refresh(db_image_gen)
        return db_image_gen

    except HTTPException:
        raise
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error during image generation"
        ) from None
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create image generation")
        raise HTTPException(
            status_code=500, detail=f"Image generation failed: {e!s}"
        ) from e


@router.get("/image-generations", response_model=list[ImageGenerationListRead])
async def list_image_generations(
    search_space_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List image generations."""
    if skip < 0 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    if limit > 100:
        limit = 100

    try:
        if search_space_id is not None:
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.IMAGE_GENERATIONS_READ.value,
                "You don't have permission to read image generations in this search space",
            )
            result = await session.execute(
                select(ImageGeneration)
                .filter(ImageGeneration.search_space_id == search_space_id)
                .order_by(ImageGeneration.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        else:
            result = await session.execute(
                select(ImageGeneration)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .order_by(ImageGeneration.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

        return [
            ImageGenerationListRead.from_orm_with_count(img)
            for img in result.scalars().all()
        ]

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error fetching image generations"
        ) from None


@router.get("/image-generations/{image_gen_id}", response_model=ImageGenerationRead)
async def get_image_generation(
    image_gen_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a specific image generation by ID."""
    try:
        result = await session.execute(
            select(ImageGeneration).filter(ImageGeneration.id == image_gen_id)
        )
        image_gen = result.scalars().first()
        if not image_gen:
            raise HTTPException(status_code=404, detail="Image generation not found")

        await check_permission(
            session,
            user,
            image_gen.search_space_id,
            Permission.IMAGE_GENERATIONS_READ.value,
            "You don't have permission to read image generations in this search space",
        )
        return image_gen

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error fetching image generation"
        ) from None


@router.delete("/image-generations/{image_gen_id}", response_model=dict)
async def delete_image_generation(
    image_gen_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete an image generation record."""
    try:
        result = await session.execute(
            select(ImageGeneration).filter(ImageGeneration.id == image_gen_id)
        )
        db_image_gen = result.scalars().first()
        if not db_image_gen:
            raise HTTPException(status_code=404, detail="Image generation not found")

        await check_permission(
            session,
            user,
            db_image_gen.search_space_id,
            Permission.IMAGE_GENERATIONS_DELETE.value,
            "You don't have permission to delete image generations in this search space",
        )

        await session.delete(db_image_gen)
        await session.commit()
        return {"message": "Image generation deleted successfully"}

    except HTTPException:
        raise
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error deleting image generation"
        ) from None


# =============================================================================
# Image Serving (serves generated images from DB, protected by signed tokens)
# =============================================================================


@router.get("/image-generations/{image_gen_id}/image")
async def serve_generated_image(
    image_gen_id: int,
    token: str = Query(..., description="Signed access token"),
    index: int = 0,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Serve a generated image by ID, protected by a signed token.

    The token is generated when the image URL is created by the generate_image
    tool and encodes the image_gen_id, search_space_id, and an expiry timestamp.
    This ensures only users with access to the search space can view images,
    without requiring auth headers (which <img> tags cannot pass).

    Args:
        image_gen_id: The image generation record ID
        token: HMAC-signed access token (included as query parameter)
        index: Which image to serve if multiple were generated (default: 0)
    """
    try:
        result = await session.execute(
            select(ImageGeneration).filter(ImageGeneration.id == image_gen_id)
        )
        image_gen = result.scalars().first()
        if not image_gen:
            raise HTTPException(status_code=404, detail="Image generation not found")

        # Verify the access token against the one stored on the record
        if not verify_image_token(image_gen.access_token, token):
            raise HTTPException(status_code=403, detail="Invalid image access token")

        if not image_gen.response_data:
            raise HTTPException(status_code=404, detail="No image data available")

        images = image_gen.response_data.get("data", [])
        if not images or index >= len(images):
            raise HTTPException(
                status_code=404, detail="Image not found at the specified index"
            )

        image_entry = images[index]

        # If there's a URL, redirect to it
        if image_entry.get("url"):
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url=image_entry["url"])

        # If there's b64_json data, decode and serve it
        if image_entry.get("b64_json"):
            image_bytes = base64.b64decode(image_entry["b64_json"])
            return Response(
                content=image_bytes,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": f'inline; filename="generated-{image_gen_id}-{index}.png"',
                },
            )

        raise HTTPException(status_code=404, detail="No displayable image data")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to serve generated image")
        raise HTTPException(
            status_code=500, detail=f"Failed to serve image: {e!s}"
        ) from e
