"""The plugins a Claude Code turn cannot use, from the statuses its `init` message reports.

Claude Code connects its MCP servers in the background and holds a turn's
`init` until each has connected or failed, within its MCP timeout, the shared
CONNECT_SECONDS: read there, a status is settled, as opencode's is once the
API's add call returns. Asked earlier, every server is still `pending`.
"""

from typing import Any

from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin

# Usable, or turned off on purpose; neither is the user's to fix.
_FINE = {"connected", "disabled"}


def unavailable_plugins(
    servers: list[dict[str, Any]], plugins: list[TurnPlugin]
) -> list[UnavailablePlugin]:
    """Each given plugin that is not connected, named as opencode's turn names it."""
    by_name = {plugin.name: plugin for plugin in plugins}
    unavailable = []
    for server in servers:
        plugin = by_name.get(server.get("name", ""))
        status = server.get("status")
        if plugin is None or status in _FINE:
            continue
        if status == "needs-auth":
            reason = "license" if plugin.licensed else "sign_in"
        else:
            # Failed, or still connecting past the timeout, as opencode's add times out.
            reason = "unreachable"
        unavailable.append(UnavailablePlugin(plugin.title, reason))
    return unavailable
