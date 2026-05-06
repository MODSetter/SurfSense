"""grep: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.filesystem.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    pat = d.get("pattern", "") if isinstance(tool_input, dict) else str(tool_input)
    grep_path = d.get("path", "") if isinstance(tool_input, dict) else ""
    display_pat = pat[:60] + ("…" if len(pat) > 60 else "")
    return ToolStartThinking(
        title="Searching content",
        items=[f'"{display_pat}"' + (f" in {grep_path}" if grep_path else "")],
    )


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_output, tool_name
    return ("Searching content", last_items)
