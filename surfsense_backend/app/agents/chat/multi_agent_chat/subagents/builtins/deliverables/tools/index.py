"""``deliverables`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset

from .generate_image import create_generate_image_tool
from .load_artifact_for_revision import create_load_artifact_for_revision_tool
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
    sandbox_tools = []
    if is_sandbox_enabled():
        sandbox_tools = [
            *create_sandbox_tools(workspace_id=d["workspace_id"]),
            create_load_artifact_for_revision_tool(
                workspace_id=d["workspace_id"],
            ),
            create_verify_artifact_tool(workspace_id=d["workspace_id"]),
        ]
    return [
        *sandbox_tools,
        create_save_artifact_tool(workspace_id=d["workspace_id"]),
        create_generate_podcast_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
        ),
        create_generate_video_presentation_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
        ),
        create_generate_image_tool(
            workspace_id=d["workspace_id"],
            db_session=d["db_session"],
            image_gen_model_id_override=d.get("image_gen_model_id_override"),
        ),
    ]
