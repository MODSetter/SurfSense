from collections.abc import Callable

from sqlalchemy.orm import Session

from modules.llm.credentials import read_provider_key
from modules.llm.providers.ollama.provider import OllamaProvider
from modules.llm.providers.openrouter.provider import OpenRouterProvider
from modules.llm.providers.protocols import Generator
from shared.config import get_llm_settings

# Name to provider. Adding one is a new folder and one line here, never a change
# to a consumer: the router resolves everything through get_provider().
REGISTRY: dict[str, Callable[[], Generator]] = {
    "ollama": lambda: OllamaProvider(get_llm_settings().ollama_base_url),
    "openrouter": lambda: OpenRouterProvider(get_llm_settings().openrouter_base_url),
}


def provider_names() -> list[str]:
    return list(REGISTRY)


def get_provider(name: str, session: Session | None = None) -> Generator | None:
    """Build the provider, and give a BYO-key one its key from the database.

    The key lookup needs a session; callers that have one (every router handler)
    pass it, so a keyed provider comes back ready to answer.
    """
    factory = REGISTRY.get(name)
    if factory is None:
        return None
    provider = factory()
    if session is not None and getattr(provider, "requires_key", False):
        provider.api_key = read_provider_key(session, provider.name)
    return provider
