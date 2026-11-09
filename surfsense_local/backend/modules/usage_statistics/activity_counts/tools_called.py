"""How many tool calls one MCP request body carries: a JSON-RPC message, or a batch of them."""

import json


def tools_called(body: bytes) -> int:
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return 0
    messages = message if isinstance(message, list) else [message]
    return sum(
        1
        for item in messages
        if isinstance(item, dict) and item.get("method") == "tools/call"
    )
