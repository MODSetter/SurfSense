from mcp.server.mcpserver import MCPServer
from starlette.datastructures import Headers

from host.tests.events import EVENTS
from mcp_server.access import Refusal


class Guard:
    """Refuses every request, noting each one it was asked about."""

    async def refusal(self, headers: Headers) -> Refusal | None:
        EVENTS.append("guard asked")
        return Refusal(401, "missing_license")


access = Guard()


def server() -> MCPServer:
    guarded = MCPServer("guarded")

    @guarded.tool()
    def search(query: str) -> str:
        """Search."""
        return f"found {query}"

    return guarded
