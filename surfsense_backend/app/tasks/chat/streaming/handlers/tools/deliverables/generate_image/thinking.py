"""generate_image: thinking-step copy."""

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
    prompt = d.get("prompt", "") if isinstance(tool_input, dict) else str(tool_input)
    return ToolStartThinking(
        title="Generating image",
        items=[f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}"],
    )


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    if isinstance(tool_output, dict) and not tool_output.get("error"):
        completed = [*items, "Image generated successfully"]
    else:
        error_msg = (
            tool_output.get("error", "Generation failed")
            if isinstance(tool_output, dict)
            else "Generation failed"
        )
        completed = [*items, f"Error: {error_msg}"]
    return ("Generating image", completed)
