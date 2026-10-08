"""The route the selected text model answers on, which opencode's provider is chosen by."""

from sqlalchemy.orm import Session

from modules.llm.catalog.remote.manifest.lookup import CallRoute
from modules.llm.connections.call_route import connection_route
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel


def selected_call_route(session: Session) -> CallRoute:
    """A local model is always /chat/completions; a remote one, as its connection says."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None or selected.connection_id is None:
        return "chat_completions"
    connection = session.get(ProviderConnection, selected.connection_id)
    if connection is None:
        return "chat_completions"
    return connection_route(connection, selected.name)
