"""What to tell the user about an error opencode reports, live or read back."""

from typing import Any

# opencode compacts a session that outgrew its window and carries on; this is
# its error when it could not, and the conversation cannot go on.
COMPACTION_FAILED = "compaction.failed"
_TOO_LONG = "The conversation is too long to continue here; start a new thread."


def error_reason(error: dict[str, Any]) -> str:
    """The sentence for an error opencode reports."""
    if error.get("type") == COMPACTION_FAILED:
        return _TOO_LONG
    return (
        error.get("message") or error.get("type") or "The agent stopped with an error."
    )
