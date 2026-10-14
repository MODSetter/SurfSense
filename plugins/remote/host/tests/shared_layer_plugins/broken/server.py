from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    raise RuntimeError("the warm-up failed")
    yield


def server() -> MCPServer:
    broken = MCPServer("broken")

    @broken.tool()
    def search(query: str) -> str:
        """Search."""
        return f"found {query}"

    return broken
