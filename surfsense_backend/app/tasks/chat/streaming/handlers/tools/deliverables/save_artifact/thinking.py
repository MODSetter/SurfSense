"""save_artifact: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.deliverables.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import ToolStartThinking


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    data = as_tool_input_dict(tool_input)
    title = data.get("title", "Document")
    revising = bool(data.get("document_id"))
    return ToolStartThinking(
        title="Revising artifact" if revising else "Saving artifact",
        items=[f"Document: {title}"],
    )


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    output = tool_output if isinstance(tool_output, dict) else {}
    title = output.get("title", "Document")
    if output.get("status") == "saved":
        return ("Saving artifact", [f"Document: {title}", "Artifact saved"])
    error = str(output.get("error", "Unknown error"))
    return ("Saving artifact", [*last_items, f"Error: {error[:80]}"])
