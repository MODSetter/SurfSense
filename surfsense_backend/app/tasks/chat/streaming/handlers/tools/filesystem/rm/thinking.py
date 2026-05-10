"""rm: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.filesystem.shared.tool_input import (
    as_tool_input_dict,
    truncate_path,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    rm_path = d.get("path", "") if isinstance(tool_input, dict) else str(tool_input)
    display = truncate_path(rm_path)
    return ToolStartThinking(title="Deleting file", items=[display] if display else [])


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_output, tool_name
    return ("Deleting file", last_items)
