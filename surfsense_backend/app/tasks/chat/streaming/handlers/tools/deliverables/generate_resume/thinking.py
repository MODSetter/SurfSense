"""generate_resume: generic thinking titles and items."""

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
    return default_thinking.resolve_completed_thinking(
        tool_name, tool_output, last_items
    )
