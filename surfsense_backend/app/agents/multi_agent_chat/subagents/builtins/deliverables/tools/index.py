from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    self_gated_tool_permission_row,
)
from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

from .generate_image import create_generate_image_tool
from .podcast import create_generate_podcast_tool
from .report import create_generate_report_tool
from .resume import create_generate_resume_tool
from .video_presentation import create_generate_video_presentation_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    podcast = create_generate_podcast_tool(
        search_space_id=resolved_dependencies["search_space_id"],
        db_session=resolved_dependencies["db_session"],
        thread_id=resolved_dependencies["thread_id"],
    )
    video = create_generate_video_presentation_tool(
        search_space_id=resolved_dependencies["search_space_id"],
        db_session=resolved_dependencies["db_session"],
        thread_id=resolved_dependencies["thread_id"],
    )
    report = create_generate_report_tool(
        search_space_id=resolved_dependencies["search_space_id"],
        thread_id=resolved_dependencies["thread_id"],
        connector_service=resolved_dependencies.get("connector_service"),
        available_connectors=resolved_dependencies.get("available_connectors"),
        available_document_types=resolved_dependencies.get("available_document_types"),
    )
    resume = create_generate_resume_tool(
        search_space_id=resolved_dependencies["search_space_id"],
        thread_id=resolved_dependencies["thread_id"],
    )
    image = create_generate_image_tool(
        search_space_id=resolved_dependencies["search_space_id"],
        db_session=resolved_dependencies["db_session"],
    )
    return {
        "allow": [
            self_gated_tool_permission_row(podcast),
            self_gated_tool_permission_row(video),
            self_gated_tool_permission_row(report),
            self_gated_tool_permission_row(resume),
            self_gated_tool_permission_row(image),
        ],
        "ask": [],
    }
