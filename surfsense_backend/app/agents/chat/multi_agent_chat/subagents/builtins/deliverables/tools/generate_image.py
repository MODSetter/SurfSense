"""Image generation via litellm; resolves model config from the workspace and returns UI-ready payloads."""

import logging
from typing import Any
from urllib.parse import urlparse

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from litellm import aimage_generation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    resolve_root_thread_id,
)
from app.artifacts.media.image.record import record as record_image
from app.capabilities.core import ActivityDescriptor
from app.db import (
    Model,
    Workspace,
    shielded_async_session,
)
from app.services.auto_model_pin_service import (
    auto_model_candidates,
    choose_auto_model_candidate,
)
from app.services.billable_calls import QuotaInsufficientError, billable_call
from app.services.image_gen_billing import resolve_billing_for_image_gen
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    is_image_gen_auto_mode,
)
from app.services.llm_service import get_global_connection, get_global_model
from app.services.model_capabilities import has_capability
from app.services.model_resolver import to_litellm

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
                result = await session.execute(
                    select(Workspace).filter(Workspace.id == workspace_id)
                )
                workspace = result.scalars().first()
                if not workspace:
                    return _failed(
                        {"error": "Workspace not found"},
                        error="Workspace not found",
                    )

                if image_gen_model_id_override is not None:
                    # Automation run: use the captured image model, insulated from
                    # later workspace changes. No workspace read needed.
                    config_id = image_gen_model_id_override or IMAGE_GEN_AUTO_MODE_ID
                else:
                    config_id = workspace.image_gen_model_id or IMAGE_GEN_AUTO_MODE_ID

                # size/quality/style are intentionally omitted: valid values
                # differ per model, so we let each model use its own defaults.
                gen_kwargs: dict[str, Any] = {}
                if n is not None and n > 1:
                    gen_kwargs["n"] = n

                if is_image_gen_auto_mode(config_id):
                    candidates = await auto_model_candidates(
                        session,
                        workspace_id=workspace_id,
                        user_id=workspace.user_id,
                        capability="image_gen",
                    )
                    if not candidates:
                        err = (
                            "No image generation models available. "
                            "Please add an image model in Settings > Image Models."
                        )
                        return _failed({"error": err}, error=err)
                    config_id = int(
                        choose_auto_model_candidate(candidates, workspace_id)["id"]
                    )

                provider_base_url: str | None = None

                if config_id < 0:
                    global_model = get_global_model(config_id)
                    if not global_model or not has_capability(
                        global_model, "image_gen"
                    ):
                        err = f"Image generation model {config_id} not found"
                        return _failed({"error": err}, error=err)
                    global_connection = get_global_connection(
                        global_model["connection_id"]
                    )
                    if not global_connection:
                        err = f"Image generation connection for model {config_id} not found"
                        return _failed({"error": err}, error=err)

                    model_string, resolved_kwargs = to_litellm(
                        global_connection,
                        global_model["model_id"],
                    )
                    gen_kwargs.update(resolved_kwargs)
                    provider_base_url = resolved_kwargs.get("api_base")
                else:
                    # Positive ID = Model + Connection
                    cfg_result = await session.execute(
                        select(Model)
                        .options(selectinload(Model.connection))
                        .filter(Model.id == config_id, Model.enabled.is_(True))
                    )
                    db_model = cfg_result.scalars().first()
                    if (
                        not db_model
                        or not db_model.connection
                        or not db_model.connection.enabled
                    ):
                        err = f"Image generation model {config_id} not found"
                        return _failed({"error": err}, error=err)
                    conn = db_model.connection
                    if (
                        conn.workspace_id is not None
                        and conn.workspace_id != workspace_id
                    ):
                        err = f"Image generation model {config_id} not found"
                        return _failed({"error": err}, error=err)
                    if conn.user_id is not None and conn.user_id != workspace.user_id:
                        err = f"Image generation model {config_id} not found"
                        return _failed({"error": err}, error=err)
                    if not has_capability(db_model, "image_gen"):
                        err = f"Model {config_id} is not image-generation capable"
                        return _failed({"error": err}, error=err)

                    model_string, resolved_kwargs = to_litellm(
                        db_model.connection,
                        db_model.model_id,
                    )
                    gen_kwargs.update(resolved_kwargs)
                    provider_base_url = resolved_kwargs.get("api_base")

                (
                    billing_tier,
                    base_model,
                    reserve_micros,
                ) = await resolve_billing_for_image_gen(session, config_id, workspace)
                async with billable_call(
                    user_id=workspace.user_id,
                    workspace_id=workspace_id,
                    billing_tier=billing_tier,
                    base_model=base_model,
                    quota_reserve_micros_override=reserve_micros,
                    usage_type="image_generation",
                    call_details={"model": base_model, "prompt": prompt[:100]},
                ):
                    response = await aimage_generation(
                        prompt=prompt, model=model_string, **gen_kwargs
                    )

                response_dict = (
                    response.model_dump()
                    if hasattr(response, "model_dump")
                    else dict(response)
                )

                for image in response_dict.get("data") or []:
                    raw_url = image.get("url") if isinstance(image, dict) else None
                    if raw_url and raw_url.startswith("/") and provider_base_url:
                        parsed = urlparse(provider_base_url)
                        image["url"] = f"{parsed.scheme}://{parsed.netloc}{raw_url}"

                saved = await record_image(
                    session,
                    workspace_id=workspace_id,
                    prompt=prompt,
                    response=response_dict,
                    provenance={
                        "model": getattr(response, "_hidden_params", {}).get("model"),
                        "image_gen_model_id": config_id,
                        "n": n,
                    },
                    thread_id=resolve_root_thread_id(runtime),
                    tool_call_id=runtime.tool_call_id,
                    committed_by_turn=True,
                )
                await session.commit()

            first_image = (response_dict.get("data") or [{}])[0]
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
