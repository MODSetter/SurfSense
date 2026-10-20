"""Listing a newly given server on whichever transport it answers, as the spec's backward compatibility says."""

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.transports import (
    NOT_STREAMABLE,
    SSE,
    STREAMABLE_HTTP,
    Transport,
)
from modules.plugins.remote.source import RemoteMcpSource


async def listed_on_either(
    url: str, headers: dict[str, str]
) -> tuple[Transport, list[SourceTool]]:
    """Streamable HTTP first; SSE only when the POST was refused as a server without it.

    Raises the Streamable HTTP refusal when neither answers, since that is the one to report.
    """
    try:
        return STREAMABLE_HTTP, await _listed(url, headers, STREAMABLE_HTTP)
    except ServerError as error:
        if error.status not in NOT_STREAMABLE:
            raise
        try:
            return SSE, await _listed(url, headers, SSE)
        except Exception:
            # Any failure there means no SSE either: the Streamable HTTP refusal says why.
            raise error from None


async def _listed(
    url: str, headers: dict[str, str], transport: Transport
) -> list[SourceTool]:
    source = RemoteMcpSource(url, headers, transport)
    try:
        return await source.list_tools()
    finally:
        await source.close()
