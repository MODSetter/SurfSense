"""generate_podcast: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.deliverables.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    podcast_title = (
        d.get("podcast_title", "SurfSense Podcast")
        if isinstance(tool_input, dict)
        else "SurfSense Podcast"
    )
    content_len = len(
        d.get("source_content", "") if isinstance(tool_input, dict) else ""
    )
    return ToolStartThinking(
        title="Generating podcast",
        items=[
            f"Title: {podcast_title}",
            f"Content: {content_len:,} characters",
            "Preparing audio generation...",
        ],
    )


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    podcast_status = (
        tool_output.get("status", "unknown")
        if isinstance(tool_output, dict)
        else "unknown"
    )
    podcast_title = (
        tool_output.get("title", "Podcast")
        if isinstance(tool_output, dict)
        else "Podcast"
    )
    if podcast_status in ("pending", "generating", "processing"):
        completed = [
            f"Title: {podcast_title}",
            "Podcast generation started",
            "Processing in background...",
        ]
    elif podcast_status == "already_generating":
        completed = [
            f"Title: {podcast_title}",
            "Podcast already in progress",
            "Please wait for it to complete",
        ]
    elif podcast_status in ("failed", "error"):
        error_msg = (
            tool_output.get("error", "Unknown error")
            if isinstance(tool_output, dict)
            else "Unknown error"
        )
        completed = [
            f"Title: {podcast_title}",
            f"Error: {error_msg[:50]}",
        ]
    elif podcast_status in ("ready", "success"):
        completed = [
            f"Title: {podcast_title}",
            "Podcast ready",
        ]
    else:
        completed = items
    return ("Generating podcast", completed)
