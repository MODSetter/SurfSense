"""Listing a newly given server over Streamable HTTP, the only transport SurfSense speaks.

A server that refuses the POST as one without Streamable HTTP is looked at once
more, with the GET an SSE client opens: one that streams is refused as speaking
only SSE, so the user is told to give its Streamable HTTP address, and one that
retired the address, as DeepWiki did its `/sse`, is said to be gone. Anything
else keeps the POST's refusal.
"""

import httpx

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.connect_refusal import GONE
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.transports import NOT_STREAMABLE, SSE_ONLY
from modules.plugins.remote.source import RemoteMcpSource

# Long enough for a server's first byte, as connecting allows a listing.
_PROBE_SECONDS = 10.0


async def listed_streamable(url: str, headers: dict[str, str]) -> list[SourceTool]:
    """Raises ServerError, with reason SSE_ONLY for a server on the older transport alone."""
    source = RemoteMcpSource(url, headers)
    try:
        return await source.list_tools()
    except ServerError as error:
        if error.status not in NOT_STREAMABLE:
            raise
        streamed = await _stream_answer(url, headers)
        if streamed == SSE_ONLY:
            raise ServerError(
                "This server speaks only the older SSE transport.",
                status=error.status,
                reason=SSE_ONLY,
            ) from error
        if streamed == GONE:
            raise ServerError(
                "This address is no longer served.", status=GONE
            ) from error
        raise
    finally:
        await source.close()


async def _stream_answer(url: str, headers: dict[str, str]) -> str | int | None:
    """SSE_ONLY for an event stream, GONE for a retired address, None for anything else."""
    try:
        async with (
            httpx.AsyncClient(timeout=_PROBE_SECONDS) as http,
            http.stream(
                "GET", url, headers={**headers, "accept": "text/event-stream"}
            ) as reply,
        ):
            kind = reply.headers.get("content-type", "")
            if reply.status_code == 200 and kind.startswith("text/event-stream"):
                return SSE_ONLY
            return GONE if reply.status_code == GONE else None
    except httpx.HTTPError:
        return None
