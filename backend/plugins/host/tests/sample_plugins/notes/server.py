from mcp.server.mcpserver import MCPServer


def server() -> MCPServer:
    notes = MCPServer("notes")

    @notes.tool()
    def search(query: str) -> str:
        """Search the notes."""
        return f"found {query}"

    return notes
