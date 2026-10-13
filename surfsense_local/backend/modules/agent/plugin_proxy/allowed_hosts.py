"""Where opencode may connect: the hosts of plugins ready now, each on its port."""

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from modules.egress.service import host_destination, require
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_hosts import plugin_hosts

HTTPS_PORT = 443


def may_connect(session: Session, host: str, port: int) -> bool:
    """Read on each connection, so a setting changed mid-turn holds from the next one.

    A host allowed is recorded as called, as every other egress is.
    """
    host = host.lower()
    for plugin_id in dict.fromkeys(tool.plugin_id for tool in list_tools(session)):
        plugin = session.get_one(InstalledPlugin, plugin_id)
        url = urlsplit(plugin.url)
        ports = {url.hostname: url.port or HTTPS_PORT}
        if any(
            host == allowed and port == ports.get(allowed, HTTPS_PORT)
            for allowed in plugin_hosts(plugin)
        ):
            require(session, host_destination(f"https://{host}"))
            return True
    return False
