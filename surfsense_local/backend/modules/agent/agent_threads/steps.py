"""One tool call the agent made, as the thread shows it: what it ran and how it went."""

from dataclasses import asdict
from typing import Any

from modules.agent.tool_endpoint.convert_document import TOOL_NAME as CONVERT_TOOL
from modules.agent.tool_endpoint.registration import SERVER
from modules.agent.tool_endpoint.rendered_label import TOOL_NAME, rendered_artifact
from modules.agent.tool_endpoint.revise_document import TOOL_NAME as REVISE_TOOL

# A shell command or a read can return a whole file; the step keeps the start.
MAX_OUTPUT_CHARS = 4000
# A step's label reads a few short inputs; a script or a file's new content
# would otherwise ride in every frame and every stored turn whole.
MAX_INPUT_CHARS = 300
# A revision's operations, or a range's rows, are new content too, nested.
MAX_INPUT_ITEMS = 20
# The label names a file by the end of its path, so a path is never cut.
_WHOLE_INPUTS = frozenset({"filePath", "path"})
# The names opencode gives SurfSense's tools that make a version, in a step.
RENDER_STEP = f"{SERVER}_{TOOL_NAME}"
REVISE_STEP = f"{SERVER}_{REVISE_TOOL}"
# A conversion's result opens the same way, naming the PDF it made.
CONVERT_STEP = f"{SERVER}_{CONVERT_TOOL}"
VERSION_STEPS = (RENDER_STEP, REVISE_STEP, CONVERT_STEP)


def step_of(part: dict[str, Any]) -> dict[str, Any]:
    """The step a tool part of opencode's describes."""
    state = part.get("state") or {}
    step: dict[str, Any] = {
        "id": part["id"],
        "tool": part.get("tool"),
        "status": state.get("status"),
        "title": state.get("title"),
        "input": _shown_input(state.get("input") or {}),
    }
    if state.get("output") is not None:
        step["output"] = str(state["output"])[:MAX_OUTPUT_CHARS]
    if state.get("error") is not None:
        step["error"] = str(state["error"])
    if step["tool"] in VERSION_STEPS:
        step["artifact"] = _rendered(state)
    return step


def _rendered(state: dict[str, Any]) -> dict[str, Any] | None:
    """The version a render made, once ready; None while it runs, when it failed or was not ready in time."""
    if state.get("status") != "completed":
        return None
    made = rendered_artifact(str(state.get("output") or ""))
    return asdict(made) if made is not None else None


def _shown_input(given: Any) -> Any:
    """Every input the call took, at any depth a long text cut to its start and a long list to its first items."""
    if not isinstance(given, dict):
        return given
    return {key: _shown(value, key) for key, value in given.items()}


def _shown(value: Any, key: str) -> Any:
    if isinstance(value, str):
        if len(value) > MAX_INPUT_CHARS and key not in _WHOLE_INPUTS:
            return value[:MAX_INPUT_CHARS] + "…"
        return value
    if isinstance(value, dict):
        return {name: _shown(item, name) for name, item in value.items()}
    if isinstance(value, list):
        # Ids stay whole: a label counts the sources a call names.
        if all(isinstance(item, int | float) for item in value):
            return value
        kept = [_shown(item, key) for item in value[:MAX_INPUT_ITEMS]]
        return [*kept, "…"] if len(value) > MAX_INPUT_ITEMS else kept
    return value
