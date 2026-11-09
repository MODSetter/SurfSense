"""A tool call the user blocked after the runtime was given its tools, refused here.

A runtime learns of a blocked tool only at its next turn, so the gateway reads which tool a
call names and answers it as a failed call; the plugin never runs it. Only a blocked or no
longer ready tool is refused: whether to ask first stays the runtime's.
"""

import json

from starlette.responses import JSONResponse, Response

REFUSAL = "The user blocked this tool in SurfSense, so it was not run."


def blocked_reply(body: bytes, ready: frozenset[str]) -> Response | None:
    """None to send the request on; a batch naming a blocked call is refused outright."""
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    messages = message if isinstance(message, list) else [message]
    blocked = [m for m in messages if _blocked(m, ready)]
    if not blocked:
        return None
    if isinstance(message, list):
        return JSONResponse({"detail": REFUSAL}, status_code=403)
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"content": [{"type": "text", "text": REFUSAL}], "isError": True},
        }
    )


def _blocked(message: object, ready: frozenset[str]) -> bool:
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return False
    params = message.get("params")
    return not isinstance(params, dict) or params.get("name") not in ready
