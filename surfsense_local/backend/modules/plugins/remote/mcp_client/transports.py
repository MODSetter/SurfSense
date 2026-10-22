"""The two ways a remote plugin's server is reached: Streamable HTTP, or the older HTTP+SSE.

Recorded on the plugin's entry when it connects, so every later listing, and the agent,
use the one that answered. An entry without one is Streamable HTTP.
"""

from typing import Any, Literal

Transport = Literal["streamable_http", "sse"]
STREAMABLE_HTTP: Transport = "streamable_http"
SSE: Transport = "sse"
# What a server without Streamable HTTP answers its POST, per the spec's backward compatibility.
NOT_STREAMABLE = {400, 404, 405}


def entry_transport(entry: dict[str, Any]) -> Transport:
    return SSE if entry.get("transport") == SSE else STREAMABLE_HTTP
