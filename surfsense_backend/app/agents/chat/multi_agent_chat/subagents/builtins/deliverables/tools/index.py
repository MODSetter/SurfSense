"""``deliverables`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.config import config
from app.deliverables.jobs.dispatch import dispatch_deliverable_job

from .enqueue_deliverable_job import create_enqueue_deliverable_job_tool
from .generate_image import create_generate_image_tool
from .load_artifact_for_revision import create_load_artifact_for_revision_tool
from .load_source_document import create_load_source_document_tool
from .podcast import create_generate_podcast_tool
from .sandbox import create_sandbox_tools
from .save_artifact import create_save_artifact_tool
from .verify_artifact import create_verify_artifact_tool
from .video_presentation import create_generate_video_presentation_tool

NAME = "deliverables"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    from app.sandbox import is_sandbox_enabled

    d = {**(dependencies or {}), **kwargs}
    # Offering these with no sandbox behind them would have the model follow the
    # prompt's skill workflow up to the first tool call, then fail.
    sandbox_enabled = is_sandbox_enabled()
    sandbox_tools = []
    if sandbox_enabled:
        sandbox_tools = [
            *create_sandbox_tools(workspace_id=d["workspace_id"]),
            create_load_artifact_for_revision_tool(
                workspace_id=d["workspace_id"],
            ),
            create_load_source_document_tool(workspace_id=d["workspace_id"]),
            create_verify_artifact_tool(workspace_id=d["workspace_id"]),
        ]

    video_tools = (
        [
            create_enqueue_deliverable_job_tool(
                workspace_id=d["workspace_id"],
                created_by_id=d.get("user_id") or d.get("created_by_id"),
                dispatcher=d.get("deliverable_job_dispatcher")
                or dispatch_deliverable_job,
            )
        ]
        if config.VIDEO_SANDBOX_RENDERING_ENABLED and sandbox_enabled
        else [
            create_generate_video_presentation_tool(
                workspace_id=d["workspace_id"],
                db_session=d["db_session"],
            )
        ]
    )
    return [
        *sandbox_tools,
        create_save_artifact_tool(workspace_id=d["workspace_id"]),
        create_generate_podcast_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
        ),
        *video_tools,
        create_generate_image_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
            image_gen_model_id_override=d.get("image_gen_model_id_override"),
        ),
    ]
