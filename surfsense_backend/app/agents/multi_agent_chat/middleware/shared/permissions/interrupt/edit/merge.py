"""Apply edited args to a tool call.

Semantics match :func:`app.agents.new_chat.tools.hitl.request_approval`'s
``final_params = {**params, **edited_params}`` — shallow merge, edited
values override originals. Keys absent from ``edited_args`` keep their
original values, so partial edits are safe.

Returns a NEW ``tool_call`` dict (the input is not mutated) so the caller
can swap it into the ``AIMessage.tool_calls`` list without aliasing.
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
