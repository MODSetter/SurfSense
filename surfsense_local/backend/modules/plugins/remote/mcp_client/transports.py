"""The older HTTP+SSE transport, which SurfSense no longer speaks.

MCP deprecated it in its 2025-03-26 revision, and opencode 2.x speaks Streamable
HTTP only, so neither engine could call a plugin reached over it. A plugin recorded
on it stays as it is, never contacted, until the user replaces it with its server's
Streamable HTTP address: nothing is moved behind the user's back.
"""

from typing import Any
from urllib.parse import urlsplit

SSE = "sse"
# What a server without Streamable HTTP answers its POST, per the spec's backward compatibility.
NOT_STREAMABLE = {400, 404, 405}
# A refusal's reason for a server that answers only on the older transport.
SSE_ONLY = "sse_only"


def recorded_on_sse(entry: dict[str, Any]) -> bool:
    return entry.get("transport") == SSE


def is_sse_address(url: str) -> bool:
    """An address ending in `/sse`, as providers' docs still give theirs; the Add dialog
    refuses the same rule as the user types."""
    return urlsplit(url).path.rstrip("/").lower().endswith("/sse")
