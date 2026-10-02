"""One tool call the agent made, as the thread shows it: what it ran and how it went."""

from typing import Any

# A shell command or a read can return a whole file; the step keeps the start.
MAX_OUTPUT_CHARS = 4000


def step_of(part: dict[str, Any]) -> dict[str, Any]:
    """The step a tool part of opencode's describes."""
    state = part.get("state") or {}
    step: dict[str, Any] = {
        "id": part["id"],
        "tool": part.get("tool"),
        "status": state.get("status"),
        "title": state.get("title"),
        "input": state.get("input") or {},
    }
    if state.get("output") is not None:
        step["output"] = str(state["output"])[:MAX_OUTPUT_CHARS]
    if state.get("error") is not None:
        step["error"] = str(state["error"])
    return step
