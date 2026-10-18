from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.llm.models import ProviderConnection

CLAUDE_PLAN = "claude_plan"
# Where every model call goes, so its egress is the one the plan asks for.
API_URL = "https://api.anthropic.com"
# The plan's models are Anthropic's, so the manifest's Anthropic entries describe them.
CATALOG_PROVIDER = "anthropic"


class ClaudePlanExistsError(Exception):
    def __init__(self) -> None:
        super().__init__("this install already has a Claude plan connection")


def add_claude_plan(session: Session, label: str) -> ProviderConnection:
    """A connection holding no credential: the user's Claude Code keeps the sign-in.

    One per install, since Claude Code holds one sign-in.
    """
    if session.scalar(
        select(ProviderConnection.id).where(ProviderConnection.auth_kind == CLAUDE_PLAN)
    ):
        raise ClaudePlanExistsError
    connection = ProviderConnection(
        label=label,
        provider="openai_compatible",
        base_url=API_URL,
        catalog_provider=CATALOG_PROVIDER,
        auth_kind=CLAUDE_PLAN,
    )
    session.add(connection)
    session.flush()
    return connection
