"""The JSON-RPC 2.0 replies opencode's client accepts: exactly the keys its parser allows."""

from typing import Any

# JSON-RPC's own codes.
UNKNOWN_METHOD = -32601
INVALID_PARAMS = -32602


def result(message: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    """A success reply to `message`."""
    return {"jsonrpc": "2.0", "id": message["id"], "result": value}


def error(message: dict[str, Any], code: int, text: str) -> dict[str, Any]:
    """A protocol error, for a request the client should not have sent."""
    return {
        "jsonrpc": "2.0",
        "id": message["id"],
        "error": {"code": code, "message": text},
    }
