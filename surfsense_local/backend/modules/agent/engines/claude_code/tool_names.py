"""Claude Code's names for tools and opencode's, so one thread shows both engines' steps alike."""

from typing import Any

from modules.agent.tool_endpoint.offered_tools import TOOLS
from modules.agent.tool_endpoint.registration import SERVER

_MCP = "mcp__"
_BUILT_IN = {"Read", "Glob", "Grep", "Write", "Edit", "Skill"}
# Claude Code's file tools name their inputs as opencode's do, but in snake case.
_INPUT_KEYS = {
    "file_path": "path",
    "old_string": "oldString",
    "new_string": "newString",
    "replace_all": "replaceAll",
}
# opencode's file tools as a prompt names them, quoted, and Claude Code's.
_FILE_TOOLS = {"`read`": "`Read`", "`grep`": "`Grep`", "`glob`": "`Glob`"}
# Longest first, so one name that begins another is never half replaced.
_SURFSENSE_NAMES = sorted(TOOLS, key=len, reverse=True)


def _clean(name: str) -> str:
    """As both Claude Code and opencode spell a server's or a tool's name."""
    return "".join(
        character
        if character.isascii() and (character.isalnum() or character in "_-")
        else "_"
        for character in name
    )


def claude_tool(server: str, tool: str) -> str:
    return f"{_MCP}{_clean(server)}__{_clean(tool)}"


def step_tool(name: str) -> str:
    """The name opencode gives the same tool: `read`, `surfsense_render_document`, `<plugin>_<tool>`."""
    if name.startswith(_MCP):
        server, _, tool = name.removeprefix(_MCP).partition("__")
        return f"{server}_{tool}"
    return name.lower()


def step_input(name: str, given: dict[str, Any]) -> dict[str, Any]:
    if name not in _BUILT_IN:
        return given
    return {_INPUT_KEYS.get(key, key): value for key, value in given.items()}


def for_claude(text: str) -> str:
    """Instructions written for opencode, with SurfSense's tools named as Claude Code lists them."""
    for tool in _SURFSENSE_NAMES:
        text = text.replace(f"{SERVER}_{tool}", claude_tool(SERVER, tool))
    for opencode, claude in _FILE_TOOLS.items():
        text = text.replace(opencode, claude)
    return text
