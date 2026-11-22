from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.server.mcpserver import MCPServer

from host.tests.events import EVENTS


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    EVENTS.append("first entered")
    try:
        yield
    finally:
        EVENTS.append("first left")


def server() -> MCPServer:
    first = MCPServer("first")

    @first.tool()
    async def wait() -> str:
        """Runs until it is stopped."""
        EVENTS.append("call started")
        try:
            await anyio.sleep(60)
        except anyio.get_cancelled_exc_class():
            EVENTS.append("call ended")
            raise
        return "done"

    return first
