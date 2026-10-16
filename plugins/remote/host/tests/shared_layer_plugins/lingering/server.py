from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.server.mcpserver import MCPServer

from host.tests.events import EVENTS


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    EVENTS.append("lingering entered")
    yield
    # A pool whose close never ends.
    EVENTS.append("lingering closing")
    await anyio.sleep_forever()


def server() -> MCPServer:
    lingering = MCPServer("lingering")

    @lingering.tool()
    def search(query: str) -> str:
        """Search."""
        return f"found {query}"

    return lingering
