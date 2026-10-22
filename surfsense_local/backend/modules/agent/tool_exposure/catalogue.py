"""Every ready plugin, one line each, in SurfSense's MCP instructions, which opencode
renders into the agent's system prompt (core/src/mcp/instructions.ts).

So nothing ready is unknown to the agent while only some of its tools are held.
Each line names a plugin's tools while there is room; a plugin always keeps its line.
"""

from dataclasses import dataclass

from modules.agent.plugin_tools.turn_plugins import opencode_tool_name

# A few thousand tokens at most, beside a prompt of about 1,500.
ROOM_CHARS = 8_000

_HEAD = (
    "# Plugins\n\n"
    "These plugins are connected. You hold some of their tools; to use one you do "
    "not see, call `surfsense_open_plugin` with the plugin's name, or "
    "`surfsense_find_tools` with what you want to do, and its tools are yours at "
    "your next step.\n\n"
)


@dataclass(frozen=True)
class CataloguedPlugin:
    plugin_id: str
    title: str
    description: str
    tools: list[str]
    reachable: bool = True


def catalogue(plugins: list[CataloguedPlugin], room: int = ROOM_CHARS) -> str:
    if not plugins:
        return ""
    lines = [_line(plugin) for plugin in plugins]
    left = room - len(_HEAD) - sum(len(line) + 1 for line in lines)
    for index, plugin in enumerate(plugins):
        if not plugin.reachable or not plugin.tools:
            continue
        names = ", ".join(opencode_tool_name(plugin.plugin_id, t) for t in plugin.tools)
        added = f". Tools: {names}"
        if len(added) > left:
            continue
        lines[index] = lines[index].removesuffix(".") + added
        left -= len(added) - 1
    return _HEAD + "\n".join(lines)


def _line(plugin: CataloguedPlugin) -> str:
    named = f"- {plugin.title} (@{plugin.plugin_id})"
    if not plugin.reachable:
        return f"{named}: cannot be reached now."
    described = plugin.description.strip().rstrip(".")
    return f"{named}: {described}." if described else f"{named}."
