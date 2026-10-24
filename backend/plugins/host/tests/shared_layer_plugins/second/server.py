from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

from host.tests.events import EVENTS


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    EVENTS.append("second entered")
    try:
        yield
    finally:
        EVENTS.append("second left")


def server() -> MCPServer:
    second = MCPServer("second")

    @second.tool()
    def search(query: str) -> str:
        """Search."""
        return f"found {query}"

    return second
