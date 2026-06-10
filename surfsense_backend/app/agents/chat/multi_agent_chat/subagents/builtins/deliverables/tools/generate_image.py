"""Image generation via litellm; resolves model config from the search space and returns UI-ready payloads."""

import hashlib
import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from litellm import aimage_generation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.config import config
from app.db import (
    ImageGeneration,
    ImageGenerationConfig,
    SearchSpace,
    shielded_async_session,
)
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    ImageGenRouterService,
    is_image_gen_auto_mode,
)
from app.services.provider_api_base import resolve_api_base
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


def _resolve_provider_prefix(provider: str, custom_provider: str | None) -> str:
    if custom_provider:
        return custom_provider
    return _PROVIDER_MAP.get(provider.upper(), provider.lower())


def _build_model_string(
    provider: str, model_name: str, custom_provider: str | None
) -> str:
    return f"{_resolve_provider_prefix(provider, custom_provider)}/{model_name}"


def _get_global_image_gen_config(config_id: int) -> dict | None:
    """Get a global image gen config by negative ID."""
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if cfg.get("id") == config_id:
            return cfg
    return None


def create_generate_image_tool(
    search_space_id: int,
    db_session: AsyncSession,
    image_generation_config_id_override: int | None = None,
):
    """Create ``generate_image`` with bound search space; DB work uses a per-call session.

    ``image_generation_config_id_override``: when set (automations running on a
    captured model), use this config id instead of reading the search space's
    live ``image_generation_config_id``.
    """
    del db_session  # tool uses a fresh per-call session instead

    @tool
    async def generate_image(
        prompt: str,
        runtime: ToolRuntime,
        n: int = 1,
    ) -> Command:
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

        def _failed(payload: dict[str, Any], *, error: str) -> Command:
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="image",
                    operation="generate",
                    status="failed",
                    preview=prompt[:200] if prompt else None,
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        try:
            # Use a per-call session so concurrent tool calls don't share an
            # AsyncSession (which is not concurrency-safe). The streaming
            # task's session is shared across every tool; without isolation,
            # autoflushes from a concurrent writer poison this tool too.
            async with shielded_async_session() as session:
                if image_generation_config_id_override is not None:
                    # Automation run: use the captured image model, insulated from
                    # later search-space changes. No search-space read needed.
                    config_id = (
                        image_generation_config_id_override or IMAGE_GEN_AUTO_MODE_ID
                    )
                else:
                    result = await session.execute(
                        select(SearchSpace).filter(SearchSpace.id == search_space_id)
                    )
                    search_space = result.scalars().first()
                    if not search_space:
                        return _failed(
                            {"error": "Search space not found"},
                            error="Search space not found",
                        )

                    config_id = (
                        search_space.image_generation_config_id
                        or IMAGE_GEN_AUTO_MODE_ID
                    )

                # size/quality/style are intentionally omitted: valid values
                # differ per model, so we let each model use its own defaults.
                gen_kwargs: dict[str, Any] = {}
                if n is not None and n > 1:
                    gen_kwargs["n"] = n

                if is_image_gen_auto_mode(config_id):
                    if not ImageGenRouterService.is_initialized():
                        err = (
                            "No image generation models configured. "
                            "Please add an image model in Settings > Image Models."
                        )
                        return _failed({"error": err}, error=err)
                    response = await ImageGenRouterService.aimage_generation(
                        prompt=prompt, model="auto", **gen_kwargs
                    )
                elif config_id < 0:
                    cfg = _get_global_image_gen_config(config_id)
                    if not cfg:
                        err = f"Image generation config {config_id} not found"
                        return _failed({"error": err}, error=err)

                    provider_prefix = _resolve_provider_prefix(
                        cfg.get("provider", ""), cfg.get("custom_provider")
                    )
                    model_string = f"{provider_prefix}/{cfg['model_name']}"
                    gen_kwargs["api_key"] = cfg.get("api_key")
                    # Defense-in-depth: an empty ``api_base`` must not fall
                    # through to LiteLLM's global ``api_base`` (e.g. Azure).
                    api_base = resolve_api_base(
                        provider=cfg.get("provider"),
                        provider_prefix=provider_prefix,
                        config_api_base=cfg.get("api_base"),
                    )
                    if api_base:
                        gen_kwargs["api_base"] = api_base
                    if cfg.get("api_version"):
                        gen_kwargs["api_version"] = cfg["api_version"]
                    if cfg.get("litellm_params"):
                        gen_kwargs.update(cfg["litellm_params"])

                    response = await aimage_generation(
                        prompt=prompt, model=model_string, **gen_kwargs
                    )
                else:
                    # Positive ID = user-created ImageGenerationConfig
                    cfg_result = await session.execute(
                        select(ImageGenerationConfig).filter(
                            ImageGenerationConfig.id == config_id
                        )
                    )
                    db_cfg = cfg_result.scalars().first()
                    if not db_cfg:
                        err = f"Image generation config {config_id} not found"
                        return _failed({"error": err}, error=err)

                    provider_prefix = _resolve_provider_prefix(
                        db_cfg.provider.value, db_cfg.custom_provider
                    )
                    model_string = f"{provider_prefix}/{db_cfg.model_name}"
                    gen_kwargs["api_key"] = db_cfg.api_key
                    # Defense-in-depth: an empty ``api_base`` must not fall
                    # through to LiteLLM's global ``api_base`` (e.g. Azure).
                    api_base = resolve_api_base(
                        provider=db_cfg.provider.value,
                        provider_prefix=provider_prefix,
                        config_api_base=db_cfg.api_base,
                    )
                    if api_base:
                        gen_kwargs["api_base"] = api_base
                    if db_cfg.api_version:
                        gen_kwargs["api_version"] = db_cfg.api_version
                    if db_cfg.litellm_params:
                        gen_kwargs.update(db_cfg.litellm_params)

                    response = await aimage_generation(
                        prompt=prompt, model=model_string, **gen_kwargs
                    )

                response_dict = (
                    response.model_dump()
                    if hasattr(response, "model_dump")
                    else dict(response)
                )

                access_token = generate_image_token()
                db_image_gen = ImageGeneration(
                    prompt=prompt,
                    model=getattr(response, "_hidden_params", {}).get("model"),
                    n=n,
                    image_generation_config_id=config_id,
                    response_data=response_dict,
                    search_space_id=search_space_id,
                    access_token=access_token,
                )
                session.add(db_image_gen)
                await session.commit()
                await session.refresh(db_image_gen)
                db_image_gen_id = db_image_gen.id

            images = response_dict.get("data", [])
            if not images:
                return _failed(
                    {"error": "No images were generated"},
                    error="No images were generated",
                )

            first_image = images[0]
            revised_prompt = first_image.get("revised_prompt", prompt)

            # b64_json (e.g. gpt-image-1) is served via our backend endpoint so
            # megabytes of base64 don't bloat the LLM context.
            if first_image.get("url"):
                image_url = first_image["url"]
            elif first_image.get("b64_json"):
                backend_url = config.BACKEND_URL or "http://localhost:8000"
                image_url = (
                    f"{backend_url}/api/v1/image-generations/"
                    f"{db_image_gen_id}/image?token={access_token}"
                )
            else:
                return _failed(
                    {"error": "No displayable image data in the response"},
                    error="No displayable image data in the response",
                )

            image_id = f"image-{hashlib.md5(image_url.encode()).hexdigest()[:12]}"

            payload = {
                "id": image_id,
                "assetId": image_url,
                "src": image_url,
                "alt": revised_prompt or prompt,
                "title": "Generated Image",
                "description": revised_prompt if revised_prompt != prompt else None,
                "domain": "ai-generated",
                "ratio": "auto",
                "generated": True,
                "prompt": prompt,
                "image_count": len(images),
            }
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="image",
                    operation="generate",
                    status="success",
                    external_id=str(db_image_gen_id),
                    verifiable_url=image_url,
                    preview=(revised_prompt or prompt)[:200],
                ),
                tool_call_id=runtime.tool_call_id,
            )

        except Exception as e:
            logger.exception("Image generation failed in tool")
            err = f"Image generation failed: {e!s}"
            return _failed(
                {"error": err, "prompt": prompt},
                error=err,
            )

    return generate_image
