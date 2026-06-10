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
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.config import config
from app.db import (
    ImageGeneration,
    Model,
    SearchSpace,
    shielded_async_session,
)
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    ImageGenRouterService,
    is_image_gen_auto_mode,
)
from app.services.model_resolver import native_connection_from_config, to_litellm
from app.utils.signed_image_urls import generate_image_token

logger = logging.getLogger(__name__)

def _get_global_image_gen_config(config_id: int) -> dict | None:
    """Get a global image gen config by negative ID."""
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if cfg.get("id") == config_id:
            return cfg
    return None


def create_generate_image_tool(
    search_space_id: int,
    db_session: AsyncSession,
    image_gen_model_id_override: int | None = None,
):
    """Create ``generate_image`` with bound search space; DB work uses a per-call session.

    ``image_gen_model_id_override``: when set (automations running on a
    captured model), use this model id instead of reading the search space's
    live ``image_gen_model_id``.
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
                if image_gen_model_id_override is not None:
                    # Automation run: use the captured image model, insulated from
                    # later search-space changes. No search-space read needed.
                    config_id = (
                        image_gen_model_id_override or IMAGE_GEN_AUTO_MODE_ID
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
                        search_space.image_gen_model_id
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

                    model_string, resolved_kwargs = to_litellm(
                        native_connection_from_config(cfg),
                        cfg["model_name"],
                    )
                    gen_kwargs.update(resolved_kwargs)

                    response = await aimage_generation(
                        prompt=prompt, model=model_string, **gen_kwargs
                    )
                else:
                    # Positive ID = Model + Connection
                    cfg_result = await session.execute(
                        select(Model)
                        .options(selectinload(Model.connection))
                        .filter(Model.id == config_id, Model.enabled.is_(True))
                    )
                    db_model = cfg_result.scalars().first()
                    if not db_model or not db_model.connection or not db_model.connection.enabled:
                        err = f"Image generation model {config_id} not found"
                        return _failed({"error": err}, error=err)
                    if not (db_model.capabilities or {}).get("image_gen"):
                        err = f"Model {config_id} is not image-generation capable"
                        return _failed({"error": err}, error=err)

                    model_string, resolved_kwargs = to_litellm(
                        db_model.connection,
                        db_model.model_id,
                    )
                    gen_kwargs.update(resolved_kwargs)

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
