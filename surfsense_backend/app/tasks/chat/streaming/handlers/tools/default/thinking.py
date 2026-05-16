"""Fallback thinking-step copy for unknown tools and connectors without custom UI."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_input
    title = tool_name.replace("_", " ").strip().capitalize() or tool_name
    return ToolStartThinking(title=title, items=[], include_items_on_frame=False)


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str]
) -> tuple[str, list[str]]:
    del tool_output
    title = tool_name.replace("_", " ").strip().capitalize() or tool_name
    return (title, last_items)
