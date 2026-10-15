from sqlalchemy import Engine

from modules.llm.connections.call_route import connection_route
from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_compatible import OpenAICompatibleChatProvider
from modules.llm.providers.openai_responses import ApiKey, ResponsesChatProvider
from modules.llm.providers.protocols import Generator
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from modules.llm.subscriptions.chatgpt.plan_models import plan_generator


def connection_generator(
    engine: Engine,
    connection: ProviderConnection,
    model: str,
    *,
    reads_images: bool = False,
) -> Generator:
    """How a connection's text model answers: the credential is the connection's,
    the route is the model's own, as its provider's manifest entry records it."""
    if connection.auth_kind == CHATGPT:
        return plan_generator(engine, connection, reads_images=reads_images)
    if connection_route(connection, model) == "responses":
        return ResponsesChatProvider(
            connection.base_url, ApiKey(connection.api_key), reads_images=reads_images
        )
    return OpenAICompatibleChatProvider(
        connection.base_url, connection.api_key, reads_images=reads_images
    )
