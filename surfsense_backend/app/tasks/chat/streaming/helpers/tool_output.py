"""Normalize filesystem tool payloads for SSE cards and messages."""

from __future__ import annotations

import json
from typing import Any


def tool_output_to_text(tool_output: Any) -> str:
    if isinstance(tool_output, dict):
        if isinstance(tool_output.get("result"), str):
            return tool_output["result"]
        if isinstance(tool_output.get("error"), str):
            return tool_output["error"]
        return json.dumps(tool_output, ensure_ascii=False)
    return str(tool_output)


def tool_output_has_error(tool_output: Any) -> bool:
    if isinstance(tool_output, dict):
        if tool_output.get("error"):
            return True
        result = tool_output.get("result")
        return bool(
            isinstance(result, str) and result.strip().lower().startswith("error:")
        )
    if isinstance(tool_output, str):
        return tool_output.strip().lower().startswith("error:")
    return False


def extract_resolved_file_path(
    *, tool_name: str, tool_output: Any, tool_input: Any | None = None
) -> str | None:
    if isinstance(tool_output, dict):
        path_value = tool_output.get("path")
        if isinstance(path_value, str) and path_value.strip():
            return path_value.strip()
    if tool_name in ("write_file", "edit_file") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and file_path.strip():
            return file_path.strip()
    return None
