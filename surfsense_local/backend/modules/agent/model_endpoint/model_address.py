from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.llm.activity import model_key
from modules.llm.catalog.remote.manifest.lookup import CallRoute
from modules.llm.connections.call_route import connection_route
from modules.llm.connections.key_headers import key_headers
from modules.llm.connections.router import allowed_connection
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp
from modules.llm.resolution import ModelResolutionError
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from shared.config import get_llm_settings


@dataclass(frozen=True)
class ModelAddress:
    """Where the selected text model answers a chat request, and under what name."""

    url: str
    headers: dict[str, str]
    name: str
    # What the model is marked in use under, so it cannot be deleted mid-turn.
    activity_key: tuple[str, ...]
    # The local runtime shares its cache with chat and Studio, so its requests
    # are admitted; a remote host has its own.
    local_runtime: bool = False
    # A ChatGPT plan's connection: its token is added per request, not stored here.
    plan_connection_id: int | None = None


class WrongRouteError(ModelResolutionError):
    """The selected model answers on the other route than the one opencode called."""

    def __init__(self, route: CallRoute) -> None:
        super().__init__(f"the selected model answers on /{route.replace('_', '/')}")


def address_selected_model(session: Session, route: CallRoute) -> ModelAddress:
    """The selected text model on `route`, reachable: a remote host only once egress allows it."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    activity_key = model_key(selected.provider, selected.name, selected.connection_id)
    if selected.provider == llamacpp.PROVIDER:
        if route != "chat_completions":
            raise WrongRouteError("chat_completions")
        router = get_llm_settings().llamacpp_base_url.rstrip("/")
        return ModelAddress(
            f"{router}/v1/chat/completions",
            {},
            selected.name,
            activity_key,
            local_runtime=True,
        )
    if selected.provider != "openai_compatible" or selected.connection_id is None:
        raise ModelResolutionError(f"unknown provider: {selected.provider}")
    connection = allowed_connection(session, selected.connection_id)
    answers_on = connection_route(connection, selected.name)
    if answers_on != route:
        raise WrongRouteError(answers_on)
    base = connection.base_url.rstrip("/")
    plan = connection.auth_kind == CHATGPT
    return ModelAddress(
        f"{base}/{'responses' if route == 'responses' else 'chat/completions'}",
        {} if plan else key_headers(base, connection.api_key),
        selected.name,
        activity_key,
        plan_connection_id=connection.id if plan else None,
    )
