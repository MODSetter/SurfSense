"""What to tell the user about an error opencode reports, live or read back."""

from typing import Any

# What opencode reports when a request is too long, then compacts and carries on from.
OVERFLOW = "ContextOverflowError"
_TOO_LONG = "The conversation is too long to continue here; start a new thread."


def error_reason(error: dict[str, Any]) -> str:
    """The sentence for an error opencode reports."""
    if error.get("name") == OVERFLOW:
        return _TOO_LONG
    return (
        (error.get("data") or {}).get("message")
        or error.get("name")
        or "The agent stopped with an error."
    )
