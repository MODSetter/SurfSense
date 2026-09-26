from collections.abc import Callable

from modules.llm.providers.llamacpp import PROVIDER, LlamaCppProvider
from modules.llm.providers.protocols import Generator
from shared.config import get_llm_settings

REGISTRY: dict[str, Callable[[], Generator]] = {
    PROVIDER: lambda: LlamaCppProvider(
        get_llm_settings().llamacpp_base_url,
        get_llm_settings().llamacpp_models_dir,
    ),
}


def provider_names() -> list[str]:
    return sorted(REGISTRY)


def get_provider(name: str) -> Generator | None:
    factory = REGISTRY.get(name)
    return factory() if factory else None
