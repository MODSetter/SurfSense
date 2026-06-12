"""Provider registry for model connections.

The provider string is the single public identity axis. This registry only
describes providers whose behavior differs from LiteLLM's native default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Transport(StrEnum):
    NATIVE = "NATIVE"
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    OLLAMA = "OLLAMA"


DiscoveryKind = Literal[
    "ollama",
    "openai_models",
    "anthropic_models",
    "bedrock_models",
    "openrouter",
    "static",
    "none",
]

AuthStyle = Literal["bearer", "x-api-key", "none", "native"]


@dataclass(frozen=True)
class ProviderSpec:
    transport: Transport
    litellm_prefix: str | None
    discovery: DiscoveryKind
    default_base_url: str | None
    base_url_required: bool
    auth_style: AuthStyle
    display_name: str | None = None


REGISTRY: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        Transport.NATIVE, "openai", "openai_models", None, False, "bearer", "OpenAI"
    ),
    "anthropic": ProviderSpec(
        Transport.NATIVE, "anthropic", "anthropic_models", None, False, "x-api-key", "Anthropic"
    ),
    "azure": ProviderSpec(
        Transport.NATIVE, "azure", "static", None, True, "native", "Azure OpenAI"
    ),
    "vertex_ai": ProviderSpec(
        Transport.NATIVE, "vertex_ai", "static", None, False, "native", "Vertex AI"
    ),
    "bedrock": ProviderSpec(
        Transport.NATIVE, "bedrock", "bedrock_models", None, False, "native", "Amazon Bedrock"
    ),
    "openrouter": ProviderSpec(
        Transport.OPENAI_COMPATIBLE,
        "openrouter",
        "openrouter",
        "https://openrouter.ai/api/v1",
        False,
        "bearer",
        "OpenRouter",
    ),
    "openai_compatible": ProviderSpec(
        Transport.OPENAI_COMPATIBLE,
        "openai",
        "openai_models",
        None,
        True,
        "bearer",
        "OpenAI-compatible provider",
    ),
    "lm_studio": ProviderSpec(
        Transport.OPENAI_COMPATIBLE,
        "openai",
        "openai_models",
        "http://host.docker.internal:1234/v1",
        True,
        "bearer",
        "LM Studio",
    ),
    "ollama_chat": ProviderSpec(
        Transport.OLLAMA,
        "ollama_chat",
        "ollama",
        "http://ollama:11434",
        True,
        "none",
        "Ollama",
    ),
}


def spec_for(provider: str | None) -> ProviderSpec:
    provider_key = (provider or "").strip()
    return REGISTRY.get(provider_key) or ProviderSpec(
        Transport.NATIVE, provider_key or "openai", "static", None, False, "native"
    )


def provider_label(provider: str | None) -> str:
    provider_key = (provider or "").strip()
    spec = spec_for(provider_key)
    if spec.display_name:
        return spec.display_name
    return provider_key.replace("_", " ").title() if provider_key else "Provider"


__all__ = ["REGISTRY", "ProviderSpec", "Transport", "provider_label", "spec_for"]
