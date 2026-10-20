"""Ready plugins with tools a turn did not offer, for want of room in the model's window.

Named to the user, and to the agent, which would otherwise call such a plugin not connected.
A mention offers every tool of it at the next message.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.plugins.gateway.listing import list_tools


@dataclass(frozen=True)
class LeftOut:
    plugin_id: str
    title: str


def left_out_plugins(session: Session, plugins: list[TurnPlugin]) -> list[LeftOut]:
    offered = {(plugin.name, tool) for plugin in plugins for tool in plugin.tools}
    left_out: dict[str, str] = {}
    for tool in list_tools(session):
        if (tool.plugin_id, tool.tool) not in offered:
            left_out.setdefault(tool.plugin_id, tool.plugin_name)
    return [LeftOut(plugin_id, title) for plugin_id, title in left_out.items()]


def left_out_note(left_out: list[LeftOut]) -> str | None:
    """What the agent is told beside the user's words, as a mention is."""
    if not left_out:
        return None
    named = ", ".join(f"{plugin.title} (@{plugin.plugin_id})" for plugin in left_out)
    return (
        f"Also connected, with tools not offered this turn to save room: {named}. "
        "If one is needed, ask the user to mention it, and all its tools are "
        "offered with their next message."
    )
