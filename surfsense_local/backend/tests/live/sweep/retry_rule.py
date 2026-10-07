"""Whether a failed run ended because the provider failed, not the model: then it is tried again and not counted.

Only the last model request of the turn that failed counts, and only when that
turn did not finish normally. A blip opencode recovered from earlier in a run,
followed by a content failure, would otherwise give one model a second roll the
others did not get.
"""

import json
import re
from typing import Any

_DROPPED = (
    "RemoteProtocolError",
    "ReadError",
    "ConnectError",
    "ReadTimeout",
    "WriteError",
)
_BUSY = re.compile(r"overloaded|rate.?limit", re.IGNORECASE)
_CONTEXT = re.compile(
    r"context length|context window|maximum context|too many tokens|"
    r"prompt is too long|exceeds the model",
    re.IGNORECASE,
)
_PROVIDER_RETURNED = "Provider returned error"


def context_overflow(exchange: dict[str, Any]) -> bool:
    """The provider refused the request as longer than the model's window."""
    return bool(_CONTEXT.search(exchange.get("error") or ""))


def transient(exchange: dict[str, Any]) -> bool:
    """A provider fault: rate limits, server errors, dropped connections, OpenRouter's wrapped upstream errors."""
    status = exchange.get("status") or 0
    error = exchange.get("error") or ""
    if context_overflow(exchange):
        return False
    if status == 429 or status >= 500:
        return True
    if error.startswith(_DROPPED):
        return True
    code = _error_code(error)
    if code is not None and (code == 429 or code >= 500):
        return True
    if _BUSY.search(error):
        return True
    return status == 400 and _PROVIDER_RETURNED in error


def turn_ended_badly(frames: list[dict[str, Any]]) -> bool:
    """The turn showed an error, or never completed."""
    kinds = {frame.get("type") for frame in frames}
    return "error" in kinds or "completed" not in kinds


def ended_by_provider(
    exchanges: list[dict[str, Any]], turns: list[dict[str, Any]]
) -> bool:
    """The last request failed transiently and its turn did not finish normally."""
    if not exchanges or not turns:
        return False
    return transient(exchanges[-1]) and turn_ended_badly(turns[-1].get("frames") or [])


def _error_code(error: str) -> int | None:
    try:
        body = json.loads(error)
    except ValueError:
        return None
    if isinstance(body, dict):
        body = body.get("error", body)
    code = body.get("code") if isinstance(body, dict) else None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None
