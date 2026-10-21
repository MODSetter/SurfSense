"""A server on the older SSE transport names where each message goes in its stream's
`endpoint` event; rewritten to point back at the gateway, so every message passes it.

An endpoint on another origin ends the stream, as the MCP SDK refuses one: a server cannot
point a runtime at a host the user did not allow.
"""

from collections.abc import AsyncIterator
from urllib.parse import quote, urljoin, urlsplit

MESSAGES = "messages"


def messages_url(gateway_url: str, path: str) -> str:
    """Where a runtime posts a message; `path` is the server's own, kept in `to`."""
    return f"{gateway_url}/{MESSAGES}?to={quote(path, safe='')}"


def server_path(server_url: str, to: str) -> str | None:
    """The server's own message URL, or None for a `to` that would leave its origin."""
    if not to.startswith("/") or to.startswith("//"):
        return None
    return urljoin(server_url, to)


async def pointed_back(
    chunks: AsyncIterator[bytes], server_url: str, gateway_url: str
) -> AsyncIterator[bytes]:
    pending = b""
    async for chunk in chunks:
        pending += chunk
        *events, pending = pending.replace(b"\r\n", b"\n").split(b"\n\n")
        for event in events:
            rewritten = _rewritten(event, server_url, gateway_url)
            if rewritten is None:
                return
            yield rewritten + b"\n\n"
    if pending:
        yield pending


def _rewritten(event: bytes, server_url: str, gateway_url: str) -> bytes | None:
    lines = event.split(b"\n")
    if b"event: endpoint" not in lines and b"event:endpoint" not in lines:
        return event
    rewritten = []
    for line in lines:
        if line.startswith(b"data:"):
            named = urljoin(server_url, line[5:].strip().decode())
            parts, server = urlsplit(named), urlsplit(server_url)
            if (parts.scheme, parts.netloc) != (server.scheme, server.netloc):
                return None
            path = parts.path + (f"?{parts.query}" if parts.query else "")
            line = b"data: " + messages_url(gateway_url, path).encode()
        rewritten.append(line)
    return b"\n".join(rewritten)
