from mcp.server.mcpserver import MCPServer


def server() -> MCPServer:
    paid = MCPServer("paid")

    @paid.tool()
    def scrape(url: str) -> str:
        """Scrape a page."""
        return f"scraped {url}"

    return paid
