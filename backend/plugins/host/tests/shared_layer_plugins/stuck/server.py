from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.server.mcpserver import MCPServer

from host.tests.events import EVENTS


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    # A warm-up awaited before the yield, which never ends.
    EVENTS.append("stuck warming")
    await anyio.sleep_forever()
    yield


def server() -> MCPServer:
    stuck = MCPServer("stuck")

    @stuck.tool()
    def search(query: str) -> str:
        """Search."""
        return f"found {query}"

    return stuck
