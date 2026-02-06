"""
Image generation tool for the SurfSense agent.

This module provides a tool that generates images using litellm.aimage_generation()
and returns the result via the existing display_image tool format so the frontend
renders the generated image inline in the chat.

Config resolution:
1. Uses the search space's image_generation_config_id preference
2. Falls back to Auto mode (router load balancing) if available
3. Supports global YAML configs (negative IDs) and user DB configs (positive IDs)
"""

import logging
from typing import Any

from langchain_core.tools import tool
from litellm import aimage_generation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import ImageGeneration, ImageGenerationConfig, SearchSpace
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    ImageGenRouterService,
    is_image_gen_auto_mode,
)
from app.utils.signed_image_urls import generate_image_token

logger = logging.getLogger(__name__)

# Provider mapping (same as routes)
_PROVIDER_MAP = {
    "OPENAI": "openai",
    "AZURE_OPENAI": "azure",
    "GOOGLE": "gemini",
    "VERTEX_AI": "vertex_ai",
    "BEDROCK": "bedrock",
    "RECRAFT": "recraft",
    "OPENROUTER": "openrouter",
    "XINFERENCE": "xinference",
    "NSCALE": "nscale",
}


def _build_model_string(
    provider: str, model_name: str, custom_provider: str | None
) -> str:
    if custom_provider:
        return f"{custom_provider}/{model_name}"
    prefix = _PROVIDER_MAP.get(provider.upper(), provider.lower())
    return f"{prefix}/{model_name}"


def _get_global_image_gen_config(config_id: int) -> dict | None:
    """Get a global image gen config by negative ID."""
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if cfg.get("id") == config_id:
            return cfg
    return None


def create_generate_image_tool(
    search_space_id: int,
    db_session: AsyncSession,
):
    """
    Factory function to create the generate_image tool.

    Args:
        search_space_id: The search space ID (for config resolution)
        db_session: Async database session
    """

    @tool
    async def generate_image(
        prompt: str,
        n: int = 1,
    ) -> dict[str, Any]:
        """
        Generate an image from a text description using AI image models.

        Use this tool when the user asks you to create, generate, draw, or make an image.
        The generated image will be displayed directly in the chat.

        Args:
            prompt: A detailed text description of the image to generate.
                    Be specific about subject, style, colors, composition, and mood.
            n: Number of images to generate (1-4). Default: 1

        Returns:
            A dictionary containing the generated image(s) for display in the chat.
        """
        try:
            # Resolve the image generation config from the search space preference
            result = await db_session.execute(
                select(SearchSpace).filter(SearchSpace.id == search_space_id)
            )
            search_space = result.scalars().first()
            if not search_space:
                return {"error": "Search space not found"}

            config_id = (
                search_space.image_generation_config_id or IMAGE_GEN_AUTO_MODE_ID
            )

            # Build generation kwargs
            # NOTE: size, quality, and style are intentionally NOT passed.
            # Different models support different values for these params
            # (e.g. DALL-E 3 wants "hd"/"standard" for quality while
            # gpt-image-1 wants "high"/"medium"/"low"; size options also
            # differ). Letting the model use its own defaults avoids errors.
            gen_kwargs: dict[str, Any] = {}
            if n is not None and n > 1:
                gen_kwargs["n"] = n

            # Call litellm based on config type
            if is_image_gen_auto_mode(config_id):
                if not ImageGenRouterService.is_initialized():
                    return {
                        "error": "No image generation models configured. "
                        "Please add an image model in Settings > Image Models."
                    }
                response = await ImageGenRouterService.aimage_generation(
                    prompt=prompt, model="auto", **gen_kwargs
                )
            elif config_id < 0:
                cfg = _get_global_image_gen_config(config_id)
                if not cfg:
                    return {"error": f"Image generation config {config_id} not found"}

                model_string = _build_model_string(
                    cfg.get("provider", ""),
                    cfg["model_name"],
                    cfg.get("custom_provider"),
                )
                gen_kwargs["api_key"] = cfg.get("api_key")
                if cfg.get("api_base"):
                    gen_kwargs["api_base"] = cfg["api_base"]
                if cfg.get("api_version"):
                    gen_kwargs["api_version"] = cfg["api_version"]
                if cfg.get("litellm_params"):
                    gen_kwargs.update(cfg["litellm_params"])

                response = await aimage_generation(
                    prompt=prompt, model=model_string, **gen_kwargs
                )
            else:
                # Positive ID = user-created ImageGenerationConfig
                cfg_result = await db_session.execute(
                    select(ImageGenerationConfig).filter(
                        ImageGenerationConfig.id == config_id
                    )
                )
                db_cfg = cfg_result.scalars().first()
                if not db_cfg:
                    return {"error": f"Image generation config {config_id} not found"}

                model_string = _build_model_string(
                    db_cfg.provider.value,
                    db_cfg.model_name,
                    db_cfg.custom_provider,
                )
                gen_kwargs["api_key"] = db_cfg.api_key
                if db_cfg.api_base:
                    gen_kwargs["api_base"] = db_cfg.api_base
                if db_cfg.api_version:
                    gen_kwargs["api_version"] = db_cfg.api_version
                if db_cfg.litellm_params:
                    gen_kwargs.update(db_cfg.litellm_params)

                response = await aimage_generation(
                    prompt=prompt, model=model_string, **gen_kwargs
                )

            # Parse the response and store in DB
            response_dict = (
                response.model_dump()
                if hasattr(response, "model_dump")
                else dict(response)
            )

            # Generate a random access token for this image
            access_token = generate_image_token()

            # Save to image_generations table for history
            db_image_gen = ImageGeneration(
                prompt=prompt,
                model=getattr(response, "_hidden_params", {}).get("model"),
                n=n,
                image_generation_config_id=config_id,
                response_data=response_dict,
                search_space_id=search_space_id,
                access_token=access_token,
            )
            db_session.add(db_image_gen)
            await db_session.commit()
            await db_session.refresh(db_image_gen)

            # Extract image URLs from response
            images = response_dict.get("data", [])
            if not images:
                return {"error": "No images were generated"}

            first_image = images[0]
            revised_prompt = first_image.get("revised_prompt", prompt)

            # Resolve image URL:
            # - If the API returned a URL, use it directly.
            # - If the API returned b64_json (e.g. gpt-image-1), serve the
            #   image through our backend endpoint to avoid bloating the
            #   LLM context with megabytes of base64 data.
            if first_image.get("url"):
                image_url = first_image["url"]
            elif first_image.get("b64_json"):
                backend_url = config.BACKEND_URL or "http://localhost:8000"
                image_url = (
                    f"{backend_url}/api/v1/image-generations/"
                    f"{db_image_gen.id}/image?token={access_token}"
                )
            else:
                return {"error": "No displayable image data in the response"}

            return {
                "src": image_url,
                "alt": revised_prompt or prompt,
                "title": "Generated Image",
                "description": revised_prompt if revised_prompt != prompt else None,
                "generated": True,
                "prompt": prompt,
                "image_count": len(images),
            }

        except Exception as e:
            logger.exception("Image generation failed in tool")
            return {
                "error": f"Image generation failed: {e!s}",
                "prompt": prompt,
            }

    return generate_image
