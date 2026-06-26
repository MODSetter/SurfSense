"""Single model-to-LiteLLM resolver.

All chat, vision, image-generation, validation, and Auto routing paths should
turn a Connection + Model into LiteLLM input through this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db import Connection

from app.services.provider_registry import Transport, spec_for


def ensure_v1(base_url: str | None) -> str | None:
    if not base_url:
        return None
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped
    return f"{stripped}/v1"


def strip_version_suffix(base_url: str | None) -> str | None:
    """Drop a trailing ``/v1`` segment from a base URL.

    Native SDK transports (e.g. Anthropic) expect the API root and append the
    version path (``/v1/messages``) themselves. A base URL that already carries
    ``/v1`` would otherwise produce ``/v1/v1/messages`` and a 404.
    """
    if not base_url:
        return None
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped[: -len("/v1")]
    return stripped


def _conn_value(conn: Connection | Mapping[str, Any], key: str) -> Any:
    if isinstance(conn, Mapping):
        return conn.get(key)
    return getattr(conn, key)


def to_litellm(
    conn: Connection | Mapping[str, Any],
    model_id: str,
) -> tuple[str, dict[str, Any]]:
    """Return ``(model_string, litellm_kwargs)`` for any model role."""
    provider = _conn_value(conn, "provider")
    base_url = _conn_value(conn, "base_url")
    api_key = _conn_value(conn, "api_key")
    extra = _conn_value(conn, "extra") or {}
    spec = spec_for(provider)

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key

    prefix = spec.litellm_prefix or str(provider)
    model_string = f"{prefix}/{model_id}" if prefix else model_id
    if base_url:
        if spec.transport == Transport.OPENAI_COMPATIBLE:
            api_base = ensure_v1(base_url)
        elif provider == "anthropic":
            # LiteLLM's Anthropic handler appends ``/v1/messages`` to api_base,
            # so a base URL ending in ``/v1`` must be reduced to the API root.
            api_base = strip_version_suffix(base_url)
        else:
            api_base = base_url.rstrip("/")
        kwargs["api_base"] = api_base

    if api_version := extra.get("api_version"):
        kwargs["api_version"] = api_version
    kwargs.update(extra.get("litellm_params", {}))
    kwargs.update(extra.get("kwargs", {}))
    if provider == "bedrock" and (
        bearer_token := kwargs.pop("aws_bearer_token_bedrock", None)
    ):
        kwargs["api_key"] = bearer_token
    return model_string, kwargs


def native_connection_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Build an in-memory connection mapping from a global config."""
    provider = str(
        config.get("provider")
        or config.get("litellm_provider")
        or config.get("custom_provider")
        or "openai"
    )
    extra: dict[str, Any] = {
        "litellm_params": config.get("litellm_params") or {},
    }
    if config.get("api_version"):
        extra["api_version"] = config.get("api_version")
    return {
        "provider": provider,
        "base_url": config.get("api_base") or None,
        "api_key": config.get("api_key") or None,
        "extra": extra,
    }


__all__ = [
    "ensure_v1",
    "native_connection_from_config",
    "strip_version_suffix",
    "to_litellm",
]
