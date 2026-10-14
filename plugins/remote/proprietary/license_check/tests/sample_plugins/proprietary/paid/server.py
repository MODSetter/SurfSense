from mcp.server.mcpserver import MCPServer

from proprietary.license_check.license_access import LicenseAccess

# As a real paid plugin: Keygen's settings come from the environment the test sets.
access = LicenseAccess()


def server() -> MCPServer:
    paid = MCPServer("paid")

    @paid.tool()
    def scrape(url: str) -> str:
        """Scrape a page."""
        return f"scraped {url}"

    return paid
