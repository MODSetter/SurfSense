"""The image generator: kind-specific steps behind the generic pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.types import Command

from app.artifacts.generation.core.registry import (
    ArtifactGenerator,
    PublicArtifactTool,
    register,
)
from app.artifacts.generation.core.result import ArtifactRef, GeneratedBytes
from app.artifacts.generation.image.executor import run_image_generation
from app.artifacts.generation.image.resolve import (
    ImageModelUnavailableError,
    ResolvedImageModel,
    resolve_anonymous_image_model,
    resolve_workspace_image_model,
)
from app.artifacts.generation.image.schemas import ImageGenRequest, ImageGenResponse
from app.artifacts.media.image.bytes import image_bytes_from_response
from app.artifacts.media.image.record import record as record_image
from app.services.image_gen_billing import resolve_billing_for_image_gen

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import Workspace


class ImageGenerator(ArtifactGenerator):
    kind = "image"
    usage_type = "image_generation"
    tool_name = "generate_image"
    tool_description = (
        "Generate an image from a text description using AI image models.\n\n"
        "Use this tool when the user asks you to create, generate, draw, or make "
        "an image. The generated image will be displayed directly in the chat.\n\n"
        "Args:\n"
        "    prompt: A detailed text description of the image to generate. Be "
        "specific about subject, style, colors, composition, and mood.\n"
        "    n: Number of images to generate (1-4). Default: 1"
    )
    receipt_type = "image"
    input_schema = ImageGenRequest
    output_schema = ImageGenResponse
    seo = PublicArtifactTool(
        title="AI Image Generator",
        description="Generate an image from a text prompt with AI.",
        seo_slug="ai-image-generator",
    )
    user_facing_errors = (ImageModelUnavailableError,)

    async def resolve_workspace(
        self, session: AsyncSession, workspace: Workspace, override: int | None
    ) -> ResolvedImageModel:
        return await resolve_workspace_image_model(
            session, workspace=workspace, image_gen_model_id_override=override
        )

    def resolve_anonymous(self) -> ResolvedImageModel:
        return resolve_anonymous_image_model()

    async def billing(
        self, session: AsyncSession, model: ResolvedImageModel, workspace: Workspace
    ) -> tuple[str, str, int]:
        return await resolve_billing_for_image_gen(session, model.config_id, workspace)

    async def run(self, model: ResolvedImageModel, req: ImageGenRequest) -> dict:
        return await run_image_generation(model, prompt=req.prompt, n=req.n)

    async def persist(
        self,
        session: AsyncSession,
        *,
        workspace_id: int,
        req: ImageGenRequest,
        model: ResolvedImageModel,
        response: dict,
        thread_id: int | None,
        tool_call_id: str | None,
        committed_by_turn: bool,
    ) -> ArtifactRef:
        saved = await record_image(
            session,
            workspace_id=workspace_id,
            prompt=req.prompt,
            response=response,
            provenance={
                "model": model.model_string,
                "image_gen_model_id": model.config_id,
                "n": req.n,
            },
            thread_id=thread_id,
            tool_call_id=tool_call_id,
            committed_by_turn=committed_by_turn,
        )
        revised = (response.get("data") or [{}])[0].get("revised_prompt")
        return ArtifactRef(
            saved=saved, workspace_id=workspace_id, revised_prompt=revised
        )

    async def to_bytes(self, response: dict) -> GeneratedBytes:
        data, mime, ext = await image_bytes_from_response(response)
        return GeneratedBytes(data=data, mime_type=mime, ext=ext)

    def rest_response(self, ref: ArtifactRef) -> ImageGenResponse:
        return ImageGenResponse.from_saved(ref.saved, workspace_id=ref.workspace_id)

    def render_success(
        self, ref: ArtifactRef, req: ImageGenRequest, tool_call_id: str
    ) -> Command:
        from app.agents.chat.multi_agent_chat.shared.receipts.command import (
            with_receipt,
        )
        from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
            make_receipt,
        )

        revised_prompt = ref.revised_prompt or req.prompt
        payload = {
            "id": f"image-artifact-{ref.saved.artifact_id}",
            "artifact_id": ref.saved.artifact_id,
            "workspace_id": ref.workspace_id,
            "alt": revised_prompt,
            "title": ref.saved.title,
            "description": revised_prompt if revised_prompt != req.prompt else None,
            "domain": "ai-generated",
            "ratio": "auto",
            "generated": True,
            "prompt": req.prompt,
        }
        return with_receipt(
            payload=payload,
            receipt=make_receipt(
                route=self.receipt_route,
                type=self.receipt_type,
                operation="generate",
                status="success",
                external_id=str(ref.saved.artifact_id),
                preview=revised_prompt[:200],
            ),
            tool_call_id=tool_call_id,
        )

    def preview(self, req: ImageGenRequest) -> str | None:
        return req.prompt[:200] if req.prompt else None

    def audit(self, req: ImageGenRequest) -> dict:
        return {"prompt": req.prompt[:100]}


register(ImageGenerator())
