"""Tool-call args for scrape_webpage thinking."""

from __future__ import annotations

from typing import Any


def as_tool_input_dict(tool_input: Any) -> dict[str, Any]:
    return tool_input if isinstance(tool_input, dict) else {}
