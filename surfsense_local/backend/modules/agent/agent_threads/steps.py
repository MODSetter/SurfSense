"""One tool call the agent made, as the thread shows it: what it ran and how it went."""

from dataclasses import asdict
from typing import Any

from modules.agent.tool_endpoint.registration import SERVER
from modules.agent.tool_endpoint.rendered_label import TOOL_NAME, rendered_artifact

# A shell command or a read can return a whole file; the step keeps the start.
MAX_OUTPUT_CHARS = 4000
# The name opencode gives SurfSense's render tool in a step.
RENDER_STEP = f"{SERVER}_{TOOL_NAME}"


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
    if step["tool"] == RENDER_STEP:
        step["artifact"] = _rendered(state)
    return step


def _rendered(state: dict[str, Any]) -> dict[str, Any] | None:
    """The version a render made, once ready; None while it runs, when it failed or was not ready in time."""
    if state.get("status") != "completed":
        return None
    made = rendered_artifact(str(state.get("output") or ""))
    return asdict(made) if made is not None else None
