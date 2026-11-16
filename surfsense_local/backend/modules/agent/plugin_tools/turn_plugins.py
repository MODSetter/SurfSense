"""The plugin servers a turn gives its runtime, and a rule for each of their tools."""

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from modules.agent.plugin_gateway.given_server import given_server
from modules.agent.plugin_gateway.ready_upstream import Upstream
from modules.agent.plugin_gateway.upstream_headers import upstream_headers
from modules.plugins.gateway.approval import needs_approval
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.plugin_host import on_plugin_host
from modules.plugins.remote.sign_in.plugin_headers import LICENSE


@dataclass(frozen=True)
class TurnPlugin:
    """One ready plugin, under its id, which opencode prefixes to each of its tools."""

    name: str
    title: str
    # The gateway's address for it and the thread's key: all a runtime is given.
    url: str
    headers: dict[str, str]
    # `<plugin>_<tool>` to `allow` or `ask`; every other tool of the plugin is denied.
    rules: dict[str, str] = field(default_factory=dict)
    # The same rules by the tool's own name, for an engine that names tools otherwise.
    tools: dict[str, str] = field(default_factory=dict)
    # On SurfSense's plugin host, whose calls run longer and which Stop can reach.
    on_plugin_host: bool = False
    # Signs in with the SurfSense license, so a refusal is the license, not a sign-in.
    licensed: bool = False
    # The server itself, for SurfSense's own requests to it; never given to a runtime.
    upstream: Upstream | None = None


def opencode_tool_name(server: str, tool: str) -> str:
    """The name opencode gives a server's tool, as its MCP client spells it."""

    def clean(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    return f"{clean(server)}_{clean(tool)}"


def turn_plugins(
    session: Session, where: tuple[int, int], launch_key: str
) -> list[TurnPlugin]:
    """Every ready plugin, with a rule for each of its ready tools; which of them a turn
    holds is the engine's to choose."""
    plugins: dict[str, TurnPlugin] = {}
    for tool in list_tools(session):
        if tool.plugin_id not in plugins:
            row = session.get_one(InstalledPlugin, tool.plugin_id)
            url, headers = given_server(row.id, where, launch_key)
            plugins[tool.plugin_id] = TurnPlugin(
                name=row.id,
                title=tool.plugin_name,
                url=url,
                headers=headers,
                on_plugin_host=on_plugin_host(row.url),
                licensed=row.credential_kind == LICENSE,
                upstream=Upstream(row.url, upstream_headers(session, row, where[1])),
            )
        rule = "ask" if needs_approval(tool) else "allow"
        name = opencode_tool_name(tool.plugin_id, tool.tool)
        plugins[tool.plugin_id].rules[name] = rule
        plugins[tool.plugin_id].tools[tool.tool] = rule
    return list(plugins.values())
