from sqlalchemy.orm import Session

from modules.llm.connections.service import DiscoveredModel, discover_models
from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_responses.errors import SignInRequiredError
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from modules.llm.subscriptions.chatgpt.plan_models import plan_models
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.locate import this_machines_claude
from modules.llm.subscriptions.claude.models import claude_models


async def connection_models(
    session: Session, connection: ProviderConnection
) -> list[DiscoveredModel]:
    """What a connection offers: its plan's list when signed in with ChatGPT,
    Claude Code's list for a Claude plan, its server's `/models` otherwise."""
    if connection.auth_kind == CHATGPT:
        return await plan_models(session.get_bind(), connection)
    if connection.auth_kind == CLAUDE_PLAN:
        binary = this_machines_claude()
        if binary is None:
            raise SignInRequiredError("Claude Code is not installed")
        return await claude_models(binary)
    return await discover_models(connection)
