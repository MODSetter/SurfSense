"""The server behind a plugin the gateway may forward to now: ready, read on every request,
so a plugin switched off or a host revoked is refused at the runtime's next request."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.agent.plugin_gateway.upstream_headers import upstream_headers
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.remote.mcp_client.transports import Transport, entry_transport
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH


@dataclass(frozen=True)
class Upstream:
    url: str
    headers: dict[str, str]
    transport: Transport
    # Signed in with an OAuth token SurfSense can refresh.
    oauth: bool = False


def ready_upstream(session: Session, plugin_id: str, thread_id: int) -> Upstream | None:
    if all(tool.plugin_id != plugin_id for tool in list_tools(session)):
        return None
    plugin = session.get_one(InstalledPlugin, plugin_id)
    return Upstream(
        plugin.url,
        upstream_headers(session, plugin, thread_id),
        entry_transport(plugin.entry),
        plugin.credential_kind == OAUTH,
    )
