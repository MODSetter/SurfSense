"""Steps that loaded a plugin's tools, named by that plugin in `loaded_plugin`.

A call to a plugin tool the agent did not hold is refused by opencode as `No tool
named "…" is currently available` and the turn goes on; the turn then holds the
plugin, and the model has it from the step after next. The refusal is no failure
of the user's, so the thread shows "Loaded Linear's tools". `surfsense_open_plugin`
and `surfsense_find_tools` reply in words opening with the plugin they loaded,
read back here, so the thread names them the same way.
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.plugins.installed.models import InstalledPlugin

LOADED_TOOL = "surfsense_loaded_tools"
_ASKING_TOOLS = ("surfsense_open_plugin", "surfsense_find_tools")
_REFUSED = re.compile(r'^No tool named "([^"]+)" is currently available')
_LOADED = re.compile(r"^Loaded (.+)'s tools; they are yours from your next step")


def loaded_reply(title: str, names: list[str]) -> str:
    """What an asking tool answers once it held a plugin's tools."""
    return f"Loaded {title}'s tools; they are yours from your next step: {', '.join(names)}."


def refused_tool(step: dict[str, Any]) -> str | None:
    """The tool a step called that opencode did not hold, if that is why it failed."""
    if step.get("status") != "error":
        return None
    found = _REFUSED.match(str(step.get("error") or ""))
    return found.group(1) if found else None


def as_loaded(step: dict[str, Any], plugin: str) -> dict[str, Any]:
    """A refused call as the thread shows it: its plugin's tools loaded."""
    shown = {k: v for k, v in step.items() if k not in ("error", "output")}
    return {
        **shown,
        "tool": LOADED_TOOL,
        "status": "completed",
        "input": {"plugin": plugin},
        "loaded_plugin": plugin,
    }


def with_loaded_plugin(step: dict[str, Any]) -> dict[str, Any]:
    """An asking tool's finished step, with the plugin its reply says it loaded."""
    if step.get("tool") not in _ASKING_TOOLS or step.get("status") != "completed":
        return step
    found = _LOADED.match(str(step.get("output") or ""))
    return {**step, "loaded_plugin": found.group(1)} if found else step


def name_loaded_steps(session: Session, turns: list[dict[str, Any]]) -> None:
    """Each read-back step that loaded a plugin, named by it."""
    plugins: dict[str, str] | None = None
    for turn in turns:
        steps = (turn.get("content") or {}).get("steps") or []
        for index, step in enumerate(steps):
            name = refused_tool(step)
            if name is None:
                steps[index] = with_loaded_plugin(step)
                continue
            if plugins is None:
                plugins = _plugin_names(session)
            title = next(
                (t for prefix, t in plugins.items() if name.startswith(prefix)), None
            )
            if title is not None:
                steps[index] = as_loaded(step, title)


def _plugin_names(session: Session) -> dict[str, str]:
    """Each connected plugin's name, by the prefix opencode gives its tools."""
    rows = session.scalars(select(InstalledPlugin)).all()
    return {
        opencode_tool_name(row.id, ""): str(row.entry.get("name") or row.id)
        for row in rows
    }
