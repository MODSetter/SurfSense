from mcp.server.mcpserver import MCPServer

from proprietary.license_check.license_access import shared_access

# As a real paid plugin: Keygen's settings come from the environment the test sets.
access = shared_access()


def server() -> MCPServer:
    paid = MCPServer("paid")

    @paid.tool()
    def scrape(url: str) -> str:
        """Scrape a page."""
        return f"scraped {url}"

    return paid
