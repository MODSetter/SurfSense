from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.llm.models import ModelRole, ProviderConnection, SelectedModel
from modules.llm.providers import get_provider
from modules.llm.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleImageProvider,
)
from modules.llm.providers.protocols import Generator, ImageGenerator


class ModelResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedGeneration:
    selection: SelectedModel
    generator: Generator


@dataclass(frozen=True)
class ResolvedImageGeneration:
    selection: SelectedModel
    generator: ImageGenerator


def resolve_generation(session: Session) -> ResolvedGeneration:
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    if selected.provider == "ollama":
        provider = get_provider("ollama")
        if provider is None:  # pragma: no cover - fixed registry invariant
            raise ModelResolutionError("Ollama provider is unavailable")
        return ResolvedGeneration(selected, provider)
    connection = _connection(session, selected)
    return ResolvedGeneration(
        selected,
        OpenAICompatibleChatProvider(connection.base_url, connection.api_key),
    )


def resolve_image_generation(session: Session) -> ResolvedImageGeneration:
    selected = session.get(SelectedModel, ModelRole.IMAGE_GENERATION)
    if selected is None:
        raise ModelResolutionError("no image model selected")
    connection = _connection(session, selected)
    return ResolvedImageGeneration(
        selected,
        OpenAICompatibleImageProvider(
            connection.id, connection.base_url, connection.api_key
        ),
    )


def _connection(
    session: Session, selected: SelectedModel
) -> ProviderConnection:
    if selected.provider != "openai_compatible" or selected.connection_id is None:
        raise ModelResolutionError(f"unknown provider: {selected.provider}")
    connection = session.get(ProviderConnection, selected.connection_id)
    if connection is None:
        raise ModelResolutionError("selected model connection no longer exists")
    return connection
