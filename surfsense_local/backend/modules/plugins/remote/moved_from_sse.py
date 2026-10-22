"""A plugin recorded on the older SSE transport, moved to its server's Streamable HTTP address.

Every provider known to serve `/sse` answers MCP at `/mcp` on the same host:
Asana, Atlassian (`/v1/mcp`), Square, Intercom, PayPal, Webflow, Neon and
DeepWiki, probed on 22 Oct 2026. So a plugin recorded with `transport: sse` and
an address ending in `/sse` is tried there at its next check. A token issued for
`/sse` need not be taken at `/mcp`, so a sign-in asked for there still moves it,
and the user signs in again; when nothing answers, the record stays to say why.
"""

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.remote.connect_refusal import SIGN_IN_STATUSES
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.transports import SSE_ONLY, recorded_on_sse
from modules.plugins.remote.source import RemoteMcpSource

Listed = list[SourceTool] | ServerError


def mcp_address(url: str) -> str | None:
    """The address ending in `/mcp` beside one ending in `/sse`; None for any other."""
    parts = urlsplit(url)
    if not parts.path.rstrip("/").endswith("/sse"):
        return None
    path = parts.path.rstrip("/").removesuffix("/sse") + "/mcp"
    return urlunsplit(parts._replace(path=path))


async def listed_where_it_moved(
    entry: dict[str, Any], url: str, headers: dict[str, str], listed: Listed
) -> tuple[str, Listed]:
    """The address to keep and what it listed; `url` and `listed` for a plugin not on SSE."""
    if not recorded_on_sse(entry):
        return url, listed
    moved = mcp_address(url)
    if moved is not None:
        source = RemoteMcpSource(moved, headers)
        try:
            return moved, await source.list_tools()
        except ServerError as error:
            if error.status in SIGN_IN_STATUSES:
                return moved, error
        finally:
            await source.close()
    return url, ServerError(
        "This server speaks only the older SSE transport.", reason=SSE_ONLY
    )


def keep_address(session: Session, plugin: InstalledPlugin, url: str) -> None:
    """Record where the plugin is reached now: a moved plugin leaves SSE behind."""
    if url == plugin.url:
        return
    plugin.url = url
    plugin.entry = {k: v for k, v in plugin.entry.items() if k != "transport"}
    session.flush()
