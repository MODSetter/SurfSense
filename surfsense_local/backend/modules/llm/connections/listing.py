import asyncio

from sqlalchemy.orm import Session

from modules.llm.connections.service import DiscoveredModel, discover_models
from modules.llm.models import ProviderConnection
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from modules.llm.subscriptions.chatgpt.plan_models import plan_models
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.models import claude_models
from modules.llm.subscriptions.claude.proxy import required_claude_proxy_url
from modules.llm.subscriptions.claude.usable_claude import usable_claude


async def connection_models(
    session: Session, connection: ProviderConnection
) -> list[DiscoveredModel]:
    """What a connection offers: its plan's list when signed in with ChatGPT,
    Claude Code's list for a Claude plan, its server's `/models` otherwise."""
    if connection.auth_kind == CHATGPT:
        return await plan_models(session.get_bind(), connection)
    if connection.auth_kind == CLAUDE_PLAN:
        binary = await asyncio.to_thread(usable_claude)
        return await claude_models(binary, required_claude_proxy_url())
    return await discover_models(connection)
