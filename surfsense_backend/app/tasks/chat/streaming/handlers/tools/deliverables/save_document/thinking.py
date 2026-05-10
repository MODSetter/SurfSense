"""save_document: thinking-step copy."""

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
    doc_title = d.get("title", "") if isinstance(tool_input, dict) else str(tool_input)
    display_title = doc_title[:60] + ("…" if len(doc_title) > 60 else "")
    return ToolStartThinking(title="Saving document", items=[display_title])


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    result_str = (
        tool_output.get("result", "")
        if isinstance(tool_output, dict)
        else str(tool_output)
    )
    is_error = "Error" in result_str
    completed = [
        *items,
        result_str[:80] if is_error else "Saved to knowledge base",
    ]
    return ("Saving document", completed)
