"""Image generation via litellm; resolves model config from the workspace and returns UI-ready payloads."""

import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    resolve_root_thread_id,
)
from app.artifacts.media.image.generation import generate_image_response
from app.artifacts.media.image.record import record as record_image
from app.capabilities.core import ActivityDescriptor
from app.db import shielded_async_session
from app.services.billable_calls import QuotaInsufficientError

logger = logging.getLogger(__name__)


def create_generate_image_tool(
    workspace_id: int,
    db_session: AsyncSession,
    image_gen_model_id_override: int | None = None,
):
    """Create ``generate_image`` with bound workspace; DB work uses a per-call session.

    ``image_gen_model_id_override``: when set (automations running on a
    captured model), use this model id instead of reading the workspace's
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

        Use this tool for standalone images that should be displayed directly
        in chat. Never use it for an infographic, visual explainer, data story,
        or process infographic; those use load_artifact_instructions("infographic").

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
                generated = await generate_image_response(
                    session,
                    workspace_id=workspace_id,
                    prompt=prompt,
                    n=n,
                    image_gen_model_id_override=image_gen_model_id_override,
                )
                saved = await record_image(
                    session,
                    workspace_id=workspace_id,
                    prompt=prompt,
                    response=generated.response,
                    provenance={
                        "model": generated.provider_model,
                        "image_gen_model_id": generated.config_id,
                        "n": n,
                    },
                    thread_id=resolve_root_thread_id(runtime),
                    tool_call_id=runtime.tool_call_id,
                    committed_by_turn=True,
                )
                await session.commit()

            first_image = (generated.response.get("data") or [{}])[0]
            revised_prompt = first_image.get("revised_prompt") or prompt

            payload = {
                "id": f"image-artifact-{saved.artifact_id}",
                "artifact_id": saved.artifact_id,
                "workspace_id": workspace_id,
                "alt": revised_prompt,
                "title": saved.title,
                "description": revised_prompt if revised_prompt != prompt else None,
                "domain": "ai-generated",
                "ratio": "auto",
                "generated": True,
                "prompt": prompt,
            }
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="deliverables",
                    type="image",
                    operation="generate",
                    status="success",
                    external_id=str(saved.artifact_id),
                    preview=revised_prompt[:200],
                ),
                tool_call_id=runtime.tool_call_id,
            )

        except QuotaInsufficientError:
            err = (
                "Out of credits for image generation. Purchase additional "
                "credits or switch to a free model."
            )
            return _failed({"error": err}, error=err)

        except Exception as e:
            logger.exception("Image generation failed in tool")
            err = f"Image generation failed: {e!s}"
            return _failed(
                {"error": err, "prompt": prompt},
                error=err,
            )

    generate_image.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Creating an image",
            completed_title="Created an image",
            category="artifact",
            icon_key="image",
            kind="generate_image",
        ).as_metadata()
    }
    return generate_image
