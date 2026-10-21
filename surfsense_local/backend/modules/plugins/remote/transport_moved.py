"""A connected server whose recorded transport stopped answering, tried on the other.

Servers move from the older SSE to Streamable HTTP; one that did is not down. Tried only
when it answered as no MCP server, never for a refusal or a server out of reach.
"""

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.transports import (
    NOT_STREAMABLE,
    SSE,
    STREAMABLE_HTTP,
    Transport,
)
from modules.plugins.remote.source import RemoteMcpSource

Listed = list[SourceTool] | ServerError


async def listed_where_it_moved(
    url: str, headers: dict[str, str], transport: Transport, listed: Listed
) -> tuple[Transport, Listed]:
    """The transport that answered, and its listing; the recorded one and `listed` otherwise."""
    if not (isinstance(listed, ServerError) and listed.status in NOT_STREAMABLE):
        return transport, listed
    other = SSE if transport == STREAMABLE_HTTP else STREAMABLE_HTTP
    source = RemoteMcpSource(url, headers, other)
    try:
        return other, await source.list_tools()
    except Exception:
        return transport, listed
    finally:
        await source.close()
