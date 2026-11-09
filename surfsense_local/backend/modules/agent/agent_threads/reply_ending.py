"""How an agent reply ended, from the outcome opencode stored for its turn.

A turn opencode finished ends with an `idle` message naming how. A Stop and a
quit both read as interrupted, and a declined approval or a quit leaves no
`idle` at all, so SurfSense notes a Stop itself.
"""

from typing import Any

from modules.agent.agent_threads.error_kind import error_kind
from modules.agent.agent_threads.error_reason import error_reason

ABORTED = "aborted"


def reply_ending(
    steps: list[dict[str, Any]],
    idle: dict[str, Any] | None,
    noted: dict[str, Any] | None,
    live: bool,
) -> dict[str, Any] | None:
    """The reply's ending as a chat reply stores it; None for one that completed
    or is still being written.

    `steps` are the turn's assistant messages, `idle` the message that closed
    it, and `noted` what SurfSense kept for the reply: a Stop.
    """
    if idle is not None:
        if idle.get("outcome") == "failed":
            return _failed(idle.get("error") or {})
        if idle.get("outcome") == "interrupted":
            return noted or {"type": "interrupted"}
        return None
    if live:
        return None
    # A turn read back from 1.x, which records no outcome, or one cut off.
    last = steps[-1] if steps else {}
    error = last.get("error")
    if error is not None and error.get("type") != ABORTED:
        return _failed(error)
    if error is None and last.get("time", {}).get("completed") is not None:
        return None
    return noted or {"type": "interrupted"}


def _failed(error: dict[str, Any]) -> dict[str, Any]:
    return {"type": "error", "kind": error_kind(error), "message": error_reason(error)}
