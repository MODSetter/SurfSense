"""The only code that speaks opencode 2.x's HTTP API: its routes, events and payloads.

The messages and events it returns are opencode's own; the agent thread's
readers take them as they are.
"""

from modules.agent.opencode_client.client import (
    OPENCODE_VERSION,
    OpencodeClient,
    OpencodeVersionError,
)
from modules.agent.opencode_client.payloads import Event

__all__ = ["OPENCODE_VERSION", "Event", "OpencodeClient", "OpencodeVersionError"]
