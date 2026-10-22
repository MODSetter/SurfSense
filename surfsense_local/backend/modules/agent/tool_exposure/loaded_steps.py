"""A call to a plugin tool the agent did not hold, shown as loading that plugin's tools.

opencode refuses it as `No tool named "…" is currently available` and goes on; the
turn then holds the plugin, and the model has it from the step after next. The
refusal is no failure of the user's, so the thread shows "Loaded Linear's tools".
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.plugins.installed.models import InstalledPlugin

LOADED_TOOL = "surfsense_loaded_tools"
_REFUSED = re.compile(r'^No tool named "([^"]+)" is currently available')


def refused_tool(step: dict[str, Any]) -> str | None:
    """The tool a step called that opencode did not hold, if that is why it failed."""
    if step.get("status") != "error":
        return None
    found = _REFUSED.match(str(step.get("error") or ""))
    return found.group(1) if found else None


def as_loaded(step: dict[str, Any], plugin: str) -> dict[str, Any]:
    """The step as the thread shows it: its plugin's tools loaded, by the plugin's name."""
    shown = {k: v for k, v in step.items() if k not in ("error", "output")}
    return {**shown, "tool": LOADED_TOOL, "status": "completed", "input": {"plugin": plugin}}


def name_loaded_steps(session: Session, turns: list[dict[str, Any]]) -> None:
    """Each read-back refusal of a connected plugin's tool, shown as its loading."""
    plugins: dict[str, str] | None = None
    for turn in turns:
        steps = (turn.get("content") or {}).get("steps") or []
        for index, step in enumerate(steps):
            name = refused_tool(step)
            if name is None:
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
