from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.manifest.lookup import CallRoute
from modules.llm.models import ProviderConnection
from modules.llm.subscriptions.chatgpt.account import CHATGPT


def connection_route(connection: ProviderConnection, model: str) -> CallRoute:
    """Where a connection's text model answers: a plan only on /responses, any
    other model where its provider's manifest entry says."""
    if connection.auth_kind == CHATGPT:
        return "responses"
    return remote_lookup().call_route(model, connection.catalog_provider)
