"""``deliverables`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset

from .generate_image import create_generate_image_tool
from .podcast import create_generate_podcast_tool
from .report import create_generate_report_tool
from .resume import create_generate_resume_tool
from .sandbox import create_sandbox_tools
from .save_artifact import create_save_artifact_tool
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
    sandbox_tools = (
        create_sandbox_tools(
            workspace_id=d["workspace_id"],
            thread_id=d["thread_id"],
        )
        if is_sandbox_enabled()
        else []
    )
    return [
        *sandbox_tools,
        create_save_artifact_tool(
            workspace_id=d["workspace_id"],
            thread_id=d["thread_id"],
        ),
        create_generate_podcast_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
            thread_id=d["thread_id"],
        ),
        create_generate_video_presentation_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
            thread_id=d["thread_id"],
        ),
        create_generate_report_tool(
            workspace_id=d["workspace_id"],
            thread_id=d["thread_id"],
            connector_service=d.get("connector_service"),
            available_connectors=d.get("available_connectors"),
            available_document_types=d.get("available_document_types"),
        ),
        create_generate_resume_tool(
            workspace_id=d["workspace_id"],
            thread_id=d["thread_id"],
        ),
        create_generate_image_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
            image_gen_model_id_override=d.get("image_gen_model_id_override"),
        ),
    ]
