"""Single model-to-LiteLLM resolver.

All chat, vision, image-generation, validation, and Auto routing paths should
turn a Connection + Model into LiteLLM input through this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from app.services.provider_api_base import resolve_api_base

if TYPE_CHECKING:
    from app.db import Connection

PROTOCOL_OLLAMA = "OLLAMA"
PROTOCOL_OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
PROTOCOL_NATIVE = "NATIVE"

NATIVE_PROVIDER_PREFIX: dict[str, str] = {
    "OPENAI": "openai",
    "ANTHROPIC": "anthropic",
    "GROQ": "groq",
    "COHERE": "cohere",
    "GOOGLE": "gemini",
    "MISTRAL": "mistral",
    "AZURE_OPENAI": "azure",
    "AZURE": "azure",
    "OPENROUTER": "openrouter",
    "COMETAPI": "cometapi",
    "XAI": "xai",
    "BEDROCK": "bedrock",
    "AWS_BEDROCK": "bedrock",
    "VERTEX_AI": "vertex_ai",
    "TOGETHER_AI": "together_ai",
    "FIREWORKS_AI": "fireworks_ai",
    "DEEPSEEK": "openai",
    "ALIBABA_QWEN": "openai",
    "MOONSHOT": "openai",
    "ZHIPU": "openai",
    "GITHUB_MODELS": "github",
    "REPLICATE": "replicate",
    "PERPLEXITY": "perplexity",
    "ANYSCALE": "anyscale",
    "DEEPINFRA": "deepinfra",
    "CEREBRAS": "cerebras",
    "SAMBANOVA": "sambanova",
    "AI21": "ai21",
    "CLOUDFLARE": "cloudflare",
    "DATABRICKS": "databricks",
    "HUGGINGFACE": "huggingface",
    "MINIMAX": "openai",
    "RECRAFT": "recraft",
    "XINFERENCE": "xinference",
    "NSCALE": "nscale",
    "CUSTOM": "custom",
}


def ensure_v1(base_url: str | None) -> str | None:
    if not base_url:
        return None
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped
    return f"{stripped}/v1"


def _conn_value(conn: Connection | Mapping[str, Any], key: str) -> Any:
    if isinstance(conn, Mapping):
        return conn.get(key)
    return getattr(conn, key)


def _protocol_value(protocol: Any) -> str:
    return getattr(protocol, "value", str(protocol))


def to_litellm(
    conn: Connection | Mapping[str, Any],
    model_id: str,
) -> tuple[str, dict[str, Any]]:
    """Return ``(model_string, litellm_kwargs)`` for any model role."""
    protocol = _protocol_value(_conn_value(conn, "protocol"))
    base_url = _conn_value(conn, "base_url")
    api_key = _conn_value(conn, "api_key")
    native_provider = _conn_value(conn, "native_provider")
    extra = _conn_value(conn, "extra") or {}

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key

    if protocol == PROTOCOL_OLLAMA:
        model_string = f"ollama_chat/{model_id}"
        if base_url:
            kwargs["api_base"] = base_url.rstrip("/")
    elif protocol == PROTOCOL_OPENAI_COMPATIBLE:
        model_string = f"openai/{model_id}"
        api_base = ensure_v1(base_url)
        if api_base:
            kwargs["api_base"] = api_base
    else:
        provider_key = (native_provider or "").upper()
        prefix = NATIVE_PROVIDER_PREFIX.get(provider_key, provider_key.lower())
        if prefix == "custom":
            custom_provider = extra.get("custom_provider") or native_provider
            model_string = f"{custom_provider}/{model_id}" if custom_provider else model_id
        else:
            model_string = f"{prefix}/{model_id}"

        api_base = resolve_api_base(
            provider=provider_key,
            provider_prefix=prefix,
            config_api_base=base_url,
        )
        if api_base:
            kwargs["api_base"] = api_base

    if api_version := extra.get("api_version"):
        kwargs["api_version"] = api_version
    kwargs.update(extra.get("litellm_params", {}))
    kwargs.update(extra.get("kwargs", {}))
    return model_string, kwargs


def native_connection_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Build an in-memory NATIVE connection mapping from a legacy/global config."""
    provider = str(config.get("provider") or config.get("custom_provider") or "CUSTOM")
    extra: dict[str, Any] = {
        "litellm_params": config.get("litellm_params") or {},
    }
    if config.get("api_version"):
        extra["api_version"] = config.get("api_version")
    if config.get("custom_provider"):
        extra["custom_provider"] = config.get("custom_provider")
    return {
        "protocol": PROTOCOL_NATIVE,
        "native_provider": provider,
        "base_url": config.get("api_base") or None,
        "api_key": config.get("api_key") or None,
        "extra": extra,
    }


__all__ = [
    "NATIVE_PROVIDER_PREFIX",
    "ensure_v1",
    "native_connection_from_config",
    "to_litellm",
]
