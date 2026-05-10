"""execute: sandbox command thinking + completion lines."""

from __future__ import annotations

import re
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
    cmd = d.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
    display_cmd = cmd[:80] + ("…" if len(cmd) > 80 else "")
    return ToolStartThinking(title="Running command", items=[f"$ {display_cmd}"])


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    raw_text = (
        tool_output.get("result", "")
        if isinstance(tool_output, dict)
        else str(tool_output)
    )
    m = re.match(r"^Exit code:\s*(\d+)", raw_text)
    exit_code_val = int(m.group(1)) if m else None
    if exit_code_val is not None and exit_code_val == 0:
        completed = [*items, "Completed successfully"]
    elif exit_code_val is not None:
        completed = [*items, f"Exit code: {exit_code_val}"]
    else:
        completed = [*items, "Finished"]
    return ("Running command", completed)
