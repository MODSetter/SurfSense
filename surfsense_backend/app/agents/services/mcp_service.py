from langchain_core.tools.base import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession


class MCPService:
    def __init__(self, user_id: int, db_session: AsyncSession):
        self.user_id = user_id
        self.db_session = db_session
        self.client = None

    async def initialize(self):
        servers = await self._load_user_mcp_servers()
        if servers:
            self.client = MultiServerMCPClient(servers)

    async def get_tools(self) -> list[BaseTool]:
        if not self.client:
            return []
        return await self.client.get_tools()

    async def _load_user_mcp_servers(self) -> dict:
        return {}
