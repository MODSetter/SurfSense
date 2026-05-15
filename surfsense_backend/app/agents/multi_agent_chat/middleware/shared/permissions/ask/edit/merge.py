"""Apply edited args to a tool call (shallow merge, no mutation).

Edited values override originals; keys absent from ``edited_args`` keep
their original values, so partial edits are safe. Returns a NEW tool-call
dict so the caller can swap it into ``AIMessage.tool_calls`` without
aliasing the live message object.
"""

from __future__ import annotations

from typing import Any


def merge_edited_args(
    tool_call: dict[str, Any], edited_args: dict[str, Any]
) -> dict[str, Any]:
    original_args = tool_call.get("args") or {}
    merged_args = {**original_args, **edited_args}
    return {**tool_call, "args": merged_args}


__all__ = ["merge_edited_args"]
