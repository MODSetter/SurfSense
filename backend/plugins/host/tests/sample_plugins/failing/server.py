from mcp.server.mcpserver import MCPServer


def server() -> MCPServer:
    failing = MCPServer("failing")

    @failing.tool()
    def explode() -> str:
        """Always fails."""
        raise RuntimeError("the plugin broke")

    return failing
