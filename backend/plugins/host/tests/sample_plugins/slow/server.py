import anyio
from mcp.server.mcpserver import MCPServer


def server() -> MCPServer:
    slow = MCPServer("slow")

    @slow.tool()
    async def wait(mark: str) -> str:
        """Runs until it is stopped, writing what happened to `mark`."""
        path = anyio.Path(mark)
        await path.write_text("started")
        try:
            await anyio.sleep(60)
        except anyio.get_cancelled_exc_class():
            with anyio.CancelScope(shield=True):
                await path.write_text("cancelled")
            raise
        return "done"

    return slow
