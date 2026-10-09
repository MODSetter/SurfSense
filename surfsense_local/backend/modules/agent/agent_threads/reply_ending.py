"""How an agent reply ended, from what opencode stored for its last step.

opencode marks a Stop and a quit alike, as an abort, so SurfSense notes a Stop
itself and reads an abort without that note as the app going away.
"""

from typing import Any

from modules.agent.agent_threads.error_kind import error_kind
from modules.agent.agent_threads.error_reason import error_reason

ABORTED = "MessageAbortedError"


def reply_ending(
    last_step: dict[str, Any], noted: dict[str, Any] | None, live: bool
) -> dict[str, Any] | None:
    """The reply's ending as a chat reply stores it; None for one that completed
    or is still being written.

    `noted` is what SurfSense kept for the reply: a Stop. An abort without one
    was the app going away, and so is a reply opencode never finished.
    """
    error = last_step.get("error")
    if error is not None:
        if error.get("name") == ABORTED:
            return noted or {"type": "interrupted"}
        return {
            "type": "error",
            "kind": error_kind(error),
            "message": error_reason(error),
        }
    if live or last_step.get("time", {}).get("completed") is not None:
        return None
    return {"type": "interrupted"}
