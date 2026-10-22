"""The older HTTP+SSE transport, which SurfSense no longer speaks.

MCP deprecated it in its 2025-03-26 revision, and opencode 2.x speaks Streamable
HTTP only, so neither engine could call a plugin reached over it. A plugin
recorded on it is moved to its server's Streamable HTTP address at its next
check (moved_from_sse.py); one that could not be keeps the record, which says why.
"""

from typing import Any

SSE = "sse"
# What a server without Streamable HTTP answers its POST, per the spec's backward compatibility.
NOT_STREAMABLE = {400, 404, 405}
# A refusal's reason for a server that answers only on the older transport.
SSE_ONLY = "sse_only"


def recorded_on_sse(entry: dict[str, Any]) -> bool:
    return entry.get("transport") == SSE
