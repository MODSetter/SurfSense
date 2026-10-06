from collections.abc import Callable
from typing import TYPE_CHECKING

from modules.llm.providers.llamacpp import PROVIDER, LlamaCppProvider
from modules.llm.providers.protocols import Generator
from shared.config import get_llm_settings

if TYPE_CHECKING:
    from modules.llm.catalog.local.engines.llamacpp.manifest_fields import SamplingSet


def _publisher_sampling(model: str, reasoning: bool | None) -> "SamplingSet | None":
    # Imported here: the catalog imports this package for the runtime's name.
    from modules.llm.catalog.local.dependencies import get_local_catalog

    return get_local_catalog().publisher_sampling(model, reasoning)


REGISTRY: dict[str, Callable[[], Generator]] = {
    PROVIDER: lambda: LlamaCppProvider(
        get_llm_settings().llamacpp_base_url,
        get_llm_settings().llamacpp_models_dir,
        publisher_sampling=_publisher_sampling,
    ),
}


def provider_names() -> list[str]:
    return sorted(REGISTRY)


def get_provider(name: str) -> Generator | None:
    factory = REGISTRY.get(name)
    return factory() if factory else None
