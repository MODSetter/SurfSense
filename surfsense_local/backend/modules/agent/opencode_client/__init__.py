"""The only code that knows opencode 1.x's HTTP API: its routes, events and payloads.

What differs in opencode 2.x lives here, so moving the pin to 2.x changes this
package and the configuration writer, and nothing that calls them.
"""

from modules.agent.opencode_client.client import (
    OPENCODE_VERSION,
    OpencodeClient,
    OpencodeVersionError,
)
from modules.agent.opencode_client.payloads import Event

__all__ = ["OPENCODE_VERSION", "Event", "OpencodeClient", "OpencodeVersionError"]
