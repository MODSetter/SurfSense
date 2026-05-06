"""Server-Sent-Events wire framing."""

from __future__ import annotations

import json
from typing import Any


def format_sse(data: Any) -> str:
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data)}\n\n"


def format_done() -> str:
    return "data: [DONE]\n\n"


def get_response_headers() -> dict[str, str]:
    return {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "x-vercel-ai-ui-message-stream": "v1",
    }
