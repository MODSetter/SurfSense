"""ls: thinking-step copy for directory listing."""

from __future__ import annotations

import ast
from typing import Any

from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    if isinstance(tool_input, dict):
        path = tool_input.get("path", "/")
    else:
        path = str(tool_input)
    return ToolStartThinking(title="Listing files", items=[path])


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    if isinstance(tool_output, dict):
        ls_output = tool_output.get("result", "")
    elif isinstance(tool_output, str):
        ls_output = tool_output
    else:
        ls_output = str(tool_output) if tool_output else ""
    file_names: list[str] = []
    if ls_output:
        paths: list[str] = []
        try:
            parsed = ast.literal_eval(ls_output)
            if isinstance(parsed, list):
                paths = [str(p) for p in parsed]
        except (ValueError, SyntaxError):
            paths = [
                line.strip() for line in ls_output.strip().split("\n") if line.strip()
            ]
        for p in paths:
            name = p.rstrip("/").split("/")[-1]
            if name and len(name) <= 40:
                file_names.append(name)
            elif name:
                file_names.append(name[:37] + "...")
    if file_names:
        if len(file_names) <= 5:
            completed = [f"[{name}]" for name in file_names]
        else:
            completed = [f"[{name}]" for name in file_names[:4]]
            completed.append(f"(+{len(file_names) - 4} more)")
    else:
        completed = ["No files found"]
    return ("Listing files", completed)
