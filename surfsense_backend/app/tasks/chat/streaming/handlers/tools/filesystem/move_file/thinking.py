"""move_file: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.filesystem.shared.tool_input import (
    as_tool_input_dict,
    truncate_middle,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    src = d.get("source_path", "") if isinstance(tool_input, dict) else ""
    dst = d.get("destination_path", "") if isinstance(tool_input, dict) else ""
    display_src = truncate_middle(src, max_len=60)
    display_dst = truncate_middle(dst, max_len=60)
    return ToolStartThinking(
        title="Moving file",
        items=[f"{display_src} → {display_dst}"] if src or dst else [],
    )


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_output, tool_name
    return ("Moving file", last_items)
