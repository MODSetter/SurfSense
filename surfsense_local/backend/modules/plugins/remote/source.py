"""`RemoteMcpSource`: what a remote plugin's MCP server lists, as the gateway records it."""

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.mcp_client.session import McpSession
from modules.plugins.remote.mcp_client.transports import STREAMABLE_HTTP, Transport


class RemoteMcpSource:
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        transport: Transport = STREAMABLE_HTTP,
    ) -> None:
        self._session = McpSession(url, headers, transport)

    async def list_tools(self) -> list[SourceTool]:
        return [
            SourceTool(
                name=tool.name,
                title=tool.title,
                description=tool.description,
                input_schema=tool.input_schema,
                annotations=tool.annotations,
            )
            for tool in await self._session.list_tools()
        ]

    async def close(self) -> None:
        await self._session.close()
