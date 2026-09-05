from collections.abc import Callable

from modules.llm.providers.ollama.provider import OllamaProvider
from modules.llm.providers.protocols import Generator
from shared.config import get_llm_settings

# Name to provider. Adding one is a new folder and one line here, never a change
# to a consumer: the router resolves everything through get_provider().
REGISTRY: dict[str, Callable[[], Generator]] = {
    "ollama": lambda: OllamaProvider(get_llm_settings().ollama_base_url),
}


def provider_names() -> list[str]:
    return list(REGISTRY)


def get_provider(name: str) -> Generator | None:
    factory = REGISTRY.get(name)
    return factory() if factory else None
