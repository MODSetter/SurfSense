"""Backend-owned artifact verification tool."""

from __future__ import annotations

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.artifacts.infographic.presets import get_visual_style
from app.artifacts.infographic.selection import read_generation_state
from app.artifacts.verification.formats.registry import (
    VerifiableArtifactFormat,
    get_format_adapter,
)
from app.artifacts.verification.receipt import sha256_bytes
from app.artifacts.verification.service import verify_artifact as verify
from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import get_registry
from app.services.llm_service import get_vision_llm

from .thread_resolver import resolve_root_thread_id


def create_verify_artifact_tool(*, workspace_id: int) -> BaseTool:
    @tool
    async def verify_artifact(
        path: str,
        format: VerifiableArtifactFormat,
        runtime: ToolRuntime,
        description: str | None = None,
        markdown_path: str | None = None,
    ) -> dict:
        """Verify a sandbox-generated artifact before saving it.

        Returns actionable findings when the artifact needs changes. A clean
        result authorizes save_artifact to use the signed verification receipt.
        Declare the artifact's semantic format independently of its physical
        filename. Mind-map PNGs require markdown_path to bind their canonical
        hierarchy. Use description for a short user-facing step title.
        """
        del description
        session = await (await get_registry()).get_session(
            resolve_root_thread_id(runtime), workspace_id
        )
        vision_llm = None
        visual_reference = None
        provenance = None
        if format == "infographic":
            if markdown_path is None:
                raise ValueError(
                    "Infographic verification requires its factual Markdown path"
                )
            generation = await read_generation_state(
                session,
                path,
                workspace_id=workspace_id,
                secret_key=app_config.SECRET_KEY,
            )
            if generation is None:
                raise ValueError(
                    "Generate the infographic through execute before verification"
                )
            image_data = await session.read_file(path)
            markdown_data = await session.read_file(markdown_path)
            if generation.png_sha256 != sha256_bytes(image_data):
                raise ValueError("The infographic changed after image generation")
            if generation.markdown_sha256 != sha256_bytes(markdown_data):
                raise ValueError(
                    "The infographic Markdown changed after image generation"
                )
            style = get_visual_style(generation.resolved_style_id)
            visual_reference = (
                markdown_data.decode("utf-8")
                + "\n\nREQUIRED VISUAL STYLE\n"
                + style.description
            )
            provenance = generation.manifest_provenance()
        if get_format_adapter(format).requires_visual_review:
            async with shielded_async_session() as db_session:
                vision_llm = await get_vision_llm(
                    db_session,
                    workspace_id,
                    usage_type="artifact_verification",
                )
        result = await verify(
            session,
            path,
            format=format,
            workspace_id=workspace_id,
            vision_llm=vision_llm,
            markdown_path=markdown_path,
            visual_reference=visual_reference,
            provenance=provenance,
        )
        return {
            "status": "verified" if result.verified else "failed",
            "findings": list(result.findings),
            "notes": list(result.notes),
            "page_count": result.page_count,
            "verification_unavailable": result.unavailable_reason,
        }

    verify_artifact.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Checking the artifact",
            completed_title="Checked the artifact",
            category="artifact",
            icon_key="badge-check",
            kind="verify_artifact",
        ).as_metadata()
    }
    return verify_artifact
