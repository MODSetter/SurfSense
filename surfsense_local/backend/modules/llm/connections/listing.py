from sqlalchemy.orm import Session

from modules.llm.connections.service import DiscoveredModel, discover_models
from modules.llm.models import ProviderConnection
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from modules.llm.subscriptions.chatgpt.plan_models import plan_models


async def connection_models(
    session: Session, connection: ProviderConnection
) -> list[DiscoveredModel]:
    """What a connection offers: its plan's list when signed in with ChatGPT,
    its server's `/models` otherwise."""
    if connection.auth_kind == CHATGPT:
        return await plan_models(session.get_bind(), connection)
    return await discover_models(connection)
