"""The plugin servers a turn gives opencode, and a rule for each of their tools."""

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from modules.agent.plugin_tools.thread_calls import CALLS_HEADER
from modules.plugins.gateway.approval import needs_approval
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.plugin_host import on_plugin_host
from modules.plugins.remote.sign_in.plugin_headers import sign_in_headers

# More tools than this crowd the model's choice and its prompt; the plugins connected first win.
MAX_TOOLS = 24


@dataclass(frozen=True)
class TurnPlugin:
    """One ready plugin, under its id, which opencode prefixes to each of its tools."""

    name: str
    title: str
    url: str
    headers: dict[str, str]
    # `<plugin>_<tool>` to `allow` or `ask`; every other tool of the plugin is denied.
    rules: dict[str, str] = field(default_factory=dict)


def opencode_tool_name(server: str, tool: str) -> str:
    """The name opencode gives a server's tool, as its MCP client spells it."""

    def clean(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    return f"{clean(server)}_{clean(tool)}"


def turn_plugins(
    session: Session,
    mentioned: frozenset[str] = frozenset(),
    calls_token: str | None = None,
) -> list[TurnPlugin]:
    """The first MAX_TOOLS ready tools, and every one past them of a plugin the user mentioned.

    A plugin on SurfSense's plugin host also gets the thread's `calls_token`, so Stop can end its calls.
    """
    ready = list_tools(session)
    chosen = ready[:MAX_TOOLS] + [
        tool for tool in ready[MAX_TOOLS:] if tool.plugin_id in mentioned
    ]
    plugins: dict[str, TurnPlugin] = {}
    for tool in chosen:
        if tool.plugin_id not in plugins:
            row = session.get_one(InstalledPlugin, tool.plugin_id)
            headers = sign_in_headers(session, row)
            if calls_token and on_plugin_host(row.url):
                headers[CALLS_HEADER] = calls_token
            plugins[tool.plugin_id] = TurnPlugin(
                name=row.id,
                title=tool.plugin_name,
                url=row.url,
                headers=headers,
            )
        rule = "ask" if needs_approval(tool) else "allow"
        name = opencode_tool_name(tool.plugin_id, tool.tool)
        plugins[tool.plugin_id].rules[name] = rule
    return list(plugins.values())
