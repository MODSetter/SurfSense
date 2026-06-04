"""Synthesise a ``ToolMessage`` for a denied tool call.

The denied call is replaced with this message so the model sees a typed
``permission_denied`` error in ``ToolMessage.additional_kwargs["error"]``
and can adjust its plan without retrying the same forbidden call.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage

from app.agents.shared.errors import StreamingError
from app.agents.new_chat.permissions import Rule


def build_deny_message(tool_call: dict[str, Any], rule: Rule) -> ToolMessage:
    err = StreamingError(
        code="permission_denied",
        retryable=False,
        suggestion=(
            f"rule permission={rule.permission!r} pattern={rule.pattern!r} "
            f"blocked this call"
        ),
    )
    return ToolMessage(
        content=(
            f"Permission denied: rule {rule.permission}/{rule.pattern} "
            f"blocked tool {tool_call.get('name')!r}."
        ),
        tool_call_id=tool_call.get("id") or "",
        name=tool_call.get("name"),
        status="error",
        additional_kwargs={"error": err.model_dump()},
    )


__all__ = ["build_deny_message"]
