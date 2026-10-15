from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only


def server() -> MCPServer:
    listing = MCPServer("listing")

    @listing.tool()
    async def products(ctx: Context, count: int) -> CallToolResult:
        """Products, each a stage of the call."""
        await stage(ctx, "searching", total=count)
        items: list[dict[str, Any]] = []
        for index in range(count):
            items.append({"title": f"p{index}", "price": index, "seller": None})
            await stage(ctx, f"product {index + 1}", done=index + 1, total=count)
        return tool_result(
            f"{count} products",
            items,
            project=lambda item: {"title": item["title"], "price": item["price"]},
            text_only=wants_text_only(ctx),
        )

    return listing
