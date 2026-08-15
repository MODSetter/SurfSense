"""Backend-owned artifact verification tool."""

from __future__ import annotations

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.artifacts.verification.service import verify_artifact as verify
from app.capabilities.core import ActivityDescriptor
from app.db import shielded_async_session
from app.sandbox import get_registry
from app.services.llm_service import get_vision_llm

from .thread_resolver import resolve_root_thread_id


def create_verify_artifact_tool(*, workspace_id: int) -> BaseTool:
    @tool
    async def verify_artifact(
        path: str,
        runtime: ToolRuntime,
        description: str | None = None,
    ) -> dict:
        """Verify a sandbox-generated PDF or office artifact before saving it.

        Returns actionable findings when the artifact needs changes. A clean
        result includes the preview path to pass to save_artifact when present.
        Use description for a short user-facing step title.
        """
        del description
        root_thread_id = resolve_root_thread_id(runtime)
        session = await (await get_registry()).get_session(root_thread_id, workspace_id)
        async with shielded_async_session() as db_session:
            vision_llm = await get_vision_llm(
                db_session,
                workspace_id,
                usage_type="artifact_verification",
            )
        result = await verify(
            session,
            path,
            workspace_id=workspace_id,
            vision_llm=vision_llm,
        )
        return {
            "status": "verified" if result.verified else "failed",
            "findings": list(result.findings),
            "notes": list(result.notes),
            "preview_path": result.preview_path,
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
