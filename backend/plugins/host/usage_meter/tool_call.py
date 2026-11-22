"""Which tool a JSON-RPC request calls; its arguments are never kept."""

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    request_id: Any
    tool: str


def tool_call(body: bytes) -> ToolCall | None:
    """A `tools/call` request's id and tool name; None for any other message."""
    try:
        message = json.loads(body)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return None
    params = message.get("params")
    name = params.get("name") if isinstance(params, dict) else None
    return ToolCall(message.get("id"), name if isinstance(name, str) else "")
