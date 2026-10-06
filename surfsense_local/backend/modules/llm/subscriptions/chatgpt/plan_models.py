from sqlalchemy import Engine

from modules.llm.connections.serves import connection_serves
from modules.llm.connections.service import DiscoveredModel
from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_responses import PlanToken, ResponsesChatProvider
from modules.llm.subscriptions.chatgpt.tokens import ConnectionAccess


def plan_generator(
    engine: Engine, connection: ProviderConnection, *, reads_images: bool = False
) -> ResponsesChatProvider:
    return ResponsesChatProvider(
        connection.base_url,
        PlanToken(ConnectionAccess(engine, connection.id)),
        reads_images=reads_images,
    )


async def plan_models(
    engine: Engine, connection: ProviderConnection
) -> list[DiscoveredModel]:
    """What the plan offers, as the plan says: every listed model fills what the
    connection serves.

    The manifest's "only on /responses" is no reason to refuse here, since
    /responses is the only way this connection answers.
    """
    models = await plan_generator(engine, connection).models()
    return sorted(
        (
            DiscoveredModel(m.name, connection_serves(connection), "declared")
            for m in models
        ),
        key=lambda model: model.name.casefold(),
    )
