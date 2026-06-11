"""Single model-to-LiteLLM resolver.

All chat, vision, image-generation, validation, and Auto routing paths should
turn a Connection + Model into LiteLLM input through this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db import Connection

PROTOCOL_OLLAMA = "OLLAMA"
PROTOCOL_OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
PROTOCOL_ANTHROPIC = "ANTHROPIC"


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


def default_litellm_provider(protocol: Any) -> str:
    protocol_value = _protocol_value(protocol)
    defaults = {
        PROTOCOL_OLLAMA: "ollama_chat",
        PROTOCOL_ANTHROPIC: "anthropic",
        PROTOCOL_OPENAI_COMPATIBLE: "openai",
    }
    return defaults.get(protocol_value, "openai")


def _execution_api_base(protocol: str, base_url: str | None) -> str | None:
    del protocol
    if not base_url:
        return None
    return base_url.rstrip("/")


def to_litellm(
    conn: Connection | Mapping[str, Any],
    model_id: str,
) -> tuple[str, dict[str, Any]]:
    """Return ``(model_string, litellm_kwargs)`` for any model role."""
    protocol = _protocol_value(_conn_value(conn, "protocol"))
    base_url = _conn_value(conn, "base_url")
    api_key = _conn_value(conn, "api_key")
    litellm_provider = (
        _conn_value(conn, "litellm_provider") or default_litellm_provider(protocol)
    )
    extra = _conn_value(conn, "extra") or {}

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key

    model_string = f"{litellm_provider}/{model_id}" if litellm_provider else model_id
    api_base = _execution_api_base(protocol, base_url)
    if api_base:
        kwargs["api_base"] = api_base

    if api_version := extra.get("api_version"):
        kwargs["api_version"] = api_version
    kwargs.update(extra.get("litellm_params", {}))
    kwargs.update(extra.get("kwargs", {}))
    return model_string, kwargs


def native_connection_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Build an in-memory connection mapping from a global config."""
    protocol = str(config.get("protocol") or PROTOCOL_OPENAI_COMPATIBLE)
    litellm_provider = str(
        config.get("litellm_provider")
        or config.get("custom_provider")
        or default_litellm_provider(protocol)
    )
    extra: dict[str, Any] = {
        "litellm_params": config.get("litellm_params") or {},
    }
    if config.get("api_version"):
        extra["api_version"] = config.get("api_version")
    return {
        "protocol": protocol,
        "litellm_provider": litellm_provider,
        "base_url": config.get("api_base") or None,
        "api_key": config.get("api_key") or None,
        "extra": extra,
    }


__all__ = [
    "default_litellm_provider",
    "ensure_v1",
    "native_connection_from_config",
    "to_litellm",
]
