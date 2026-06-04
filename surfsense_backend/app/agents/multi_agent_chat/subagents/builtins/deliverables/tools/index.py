"""``deliverables`` native tools and (empty) permission ruleset.

Tools self-gate via :func:`request_approval` in their bodies.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.shared.permissions import Ruleset

from .generate_image import create_generate_image_tool
from .podcast import create_generate_podcast_tool
from .report import create_generate_report_tool
from .resume import create_generate_resume_tool
from .video_presentation import create_generate_video_presentation_tool

NAME = "deliverables"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return [
        create_generate_podcast_tool(
            search_space_id=d["search_space_id"],
            db_session=d["db_session"],
            thread_id=d["thread_id"],
        ),
        create_generate_video_presentation_tool(
            search_space_id=d["search_space_id"],
            db_session=d["db_session"],
            thread_id=d["thread_id"],
        ),
        create_generate_report_tool(
            search_space_id=d["search_space_id"],
            thread_id=d["thread_id"],
            connector_service=d.get("connector_service"),
            available_connectors=d.get("available_connectors"),
            available_document_types=d.get("available_document_types"),
        ),
        create_generate_resume_tool(
            search_space_id=d["search_space_id"],
            thread_id=d["thread_id"],
        ),
        create_generate_image_tool(
            search_space_id=d["search_space_id"],
            db_session=d["db_session"],
            image_generation_config_id_override=d.get(
                "image_generation_config_id_override"
            ),
        ),
    ]
