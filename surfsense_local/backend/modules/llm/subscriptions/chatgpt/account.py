from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.llm.models import ProviderConnection
from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from modules.llm.subscriptions.chatgpt.tokens import write_tokens

CHATGPT = "chatgpt"
# The plan's models are OpenAI's, so the manifest's OpenAI entries describe them.
CATALOG_PROVIDER = "openai"


class LabelTakenError(Exception):
    def __init__(self) -> None:
        super().__init__("a connection with this label already exists")


class NotChatGPTError(LookupError):
    def __init__(self) -> None:
        super().__init__("no ChatGPT connection has this id")


def require_free_label(session: Session, label: str) -> None:
    taken = session.scalar(
        select(ProviderConnection.id).where(
            func.lower(ProviderConnection.label) == label.lower()
        )
    )
    if taken is not None:
        raise LabelTakenError


def chatgpt_connection(session: Session, connection_id: int) -> ProviderConnection:
    connection = session.get(ProviderConnection, connection_id)
    if connection is None or connection.auth_kind != CHATGPT:
        raise NotChatGPTError
    return connection


def save_sign_in(
    session: Session, tokens: TokenSet, *, label: str | None, connection_id: int | None
) -> int:
    """Store a finished sign-in on the connection it renews, or on a new one."""
    if connection_id is not None:
        connection = chatgpt_connection(session, connection_id)
    else:
        assert label is not None
        require_free_label(session, label)
        connection = ProviderConnection(
            label=label,
            provider="openai_compatible",
            base_url=get_endpoints().api_url,
            catalog_provider=CATALOG_PROVIDER,
            auth_kind=CHATGPT,
        )
        session.add(connection)
    write_tokens(connection, tokens)
    session.flush()
    return connection.id


def sign_out(session: Session, connection_id: int) -> None:
    """Forget the tokens and keep the connection, so its selection survives."""
    write_tokens(chatgpt_connection(session, connection_id), None)
    session.flush()
