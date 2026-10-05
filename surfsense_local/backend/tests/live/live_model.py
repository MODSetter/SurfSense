"""Which model a live run calls, and through which provider: SURFSENSE_LIVE_MODEL and SURFSENSE_LIVE_PROVIDER.

The default is Claude Sonnet 5.5 on Anthropic's OpenAI-compatible API, as before the ladder.
"""

import os
from dataclasses import dataclass

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.reads_images import remote_reads_images
from tests.live.model_prices import (
    OPENROUTER_MODELS,
    Prices,
    anthropic_prices,
    openrouter_prices,
)

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_PROVIDER = "anthropic"


@dataclass(frozen=True)
class Provider:
    name: str
    # Shown on the connection, as the user would name it.
    label: str
    key_env: str
    # The remote manifest's provider id: the app reads the model's row, image input included, through it.
    catalog_provider: str


PROVIDERS = {
    "anthropic": Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY", "anthropic"),
    "openrouter": Provider(
        "openrouter", "OpenRouter", "OPENROUTER_API_KEY", "openrouter"
    ),
}


@dataclass(frozen=True)
class LiveModel:
    name: str
    provider: Provider
    prices: Prices

    @property
    def label(self) -> str:
        """The ledger's name for it: one model through two providers is two entries."""
        return f"{self.provider.name}/{self.name}"

    @property
    def upstream(self) -> str:
        """The base URL the app's catalog gives the provider."""
        provider = remote_lookup().manifest.providers[self.provider.catalog_provider]
        assert provider.connect.base_url, f"{provider} has no base URL"
        return provider.connect.base_url.rstrip("/")

    @property
    def reads_images(self) -> bool:
        """Whether the app will declare image input for it, from the same manifest row."""
        return remote_reads_images(self.name, self.provider.catalog_provider)


def chosen_provider() -> Provider:
    """The provider alone, which the skip needs before any price is read."""
    name = os.environ.get("SURFSENSE_LIVE_PROVIDER") or DEFAULT_PROVIDER
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"SURFSENSE_LIVE_PROVIDER={name} is not one of {', '.join(PROVIDERS)}"
        ) from None


def chosen_model(openrouter_listing: str = OPENROUTER_MODELS) -> LiveModel:
    """The model and its prices; an OpenRouter model's are read from its listing now."""
    provider = chosen_provider()
    name = os.environ.get("SURFSENSE_LIVE_MODEL") or DEFAULT_MODEL
    if provider.name == "openrouter":
        prices = openrouter_prices(name, openrouter_listing)
    else:
        prices = anthropic_prices(name)
    return LiveModel(name, provider, prices)
