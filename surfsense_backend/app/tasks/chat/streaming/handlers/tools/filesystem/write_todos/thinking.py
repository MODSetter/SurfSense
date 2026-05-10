"""write_todos: thinking-step copy."""

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
    todos = d.get("todos", []) if isinstance(tool_input, dict) else []
    todo_count = len(todos) if isinstance(todos, list) else 0
    return ToolStartThinking(
        title="Planning tasks",
        items=(
            [f"{todo_count} task{'s' if todo_count != 1 else ''}"] if todo_count else []
        ),
    )


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_output, tool_name
    return ("Planning tasks", last_items)
