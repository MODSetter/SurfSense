"""Extract todos from a deepagents ``TodoListMiddleware`` ``Command`` output."""

from __future__ import annotations

from typing import Any


def extract_todos_from_deepagents(command_output: Any) -> dict:
    """Normalize todos out of a deepagents ``Command`` or dict payload.

    deepagents returns a ``Command`` whose ``update['todos']`` is a list of
    ``{'content': str, 'status': str}`` dicts. The UI expects the same shape,
    so no transformation is required — only extraction.
    """
    todos_data: list = []
    if hasattr(command_output, "update"):
        update = command_output.update
        todos_data = update.get("todos", [])
    elif isinstance(command_output, dict):
        if "todos" in command_output:
            todos_data = command_output.get("todos", [])
        elif "update" in command_output and isinstance(
            command_output["update"], dict
        ):
            todos_data = command_output["update"].get("todos", [])

    return {"todos": todos_data}
