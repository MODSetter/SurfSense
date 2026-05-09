"""generate_video_presentation: generic in-progress thinking; completion is status-driven."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.default import (
    thinking as default_thinking,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    return default_thinking.resolve_start_thinking(tool_name, tool_input)


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    vp_status = (
        tool_output.get("status", "unknown")
        if isinstance(tool_output, dict)
        else "unknown"
    )
    vp_title = (
        tool_output.get("title", "Presentation")
        if isinstance(tool_output, dict)
        else "Presentation"
    )
    if vp_status in ("pending", "generating"):
        completed = [
            f"Title: {vp_title}",
            "Presentation generation started",
            "Processing in background...",
        ]
    elif vp_status == "failed":
        error_msg = (
            tool_output.get("error", "Unknown error")
            if isinstance(tool_output, dict)
            else "Unknown error"
        )
        completed = [
            f"Title: {vp_title}",
            f"Error: {error_msg[:50]}",
        ]
    else:
        completed = items
    return ("Generating video presentation", completed)
