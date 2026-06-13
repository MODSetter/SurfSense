"""Materialize server-owned GLOBAL YAML configs as virtual connections/models."""

from __future__ import annotations

from typing import Any

from app.services.model_resolver import native_connection_from_config


def _base_model(config: dict[str, Any]) -> str | None:
    litellm_params = config.get("litellm_params") or {}
    if isinstance(litellm_params, dict):
        return litellm_params.get("base_model")
    return None


def _connection_key(conn: dict[str, Any]) -> tuple[Any, ...]:
    # Deliberately includes api_key because two operator-owned credentials for
    # the same provider/base can have different quota/rate limits upstream.
    return (
        conn.get("provider"),
        conn.get("base_url"),
        conn.get("api_key"),
        _freeze(conn.get("extra") or {}),
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(val)) for key, val in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _catalog_metadata(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "billing_tier": config.get("billing_tier", "free"),
        "quota_reserve_tokens": config.get("quota_reserve_tokens"),
        "rpm": config.get("rpm"),
        "tpm": config.get("tpm"),
        "anonymous_enabled": config.get("anonymous_enabled", False),
        "seo_enabled": config.get("seo_enabled", False),
        "seo_slug": config.get("seo_slug"),
        "input_cost_per_token": (config.get("litellm_params") or {}).get(
            "input_cost_per_token"
        )
        if isinstance(config.get("litellm_params"), dict)
        else None,
        "output_cost_per_token": (config.get("litellm_params") or {}).get(
            "output_cost_per_token"
        )
        if isinstance(config.get("litellm_params"), dict)
        else None,
        "is_planner": config.get("is_planner", False),
        "base_model": _base_model(config),
        "router_pool_eligible": config.get("router_pool_eligible", True),
    }


def materialize_global_model_catalog(
    *,
    chat_configs: list[dict[str, Any]],
    image_configs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connections: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    connection_id_by_key: dict[tuple[Any, ...], int] = {}
    next_connection_id = -1

    def add_config(config: dict[str, Any], role: str) -> None:
        nonlocal next_connection_id
        if not config.get("id") or not config.get("model_name"):
            return
        conn = native_connection_from_config(config)
        conn["scope"] = "GLOBAL"
        conn["enabled"] = True
        key = _connection_key(conn)
        connection_id = connection_id_by_key.get(key)
        if connection_id is None:
            connection_id = next_connection_id
            next_connection_id -= 1
            connection_id_by_key[key] = connection_id
            connections.append(
                {
                    "id": connection_id,
                    **conn,
                }
            )

        model_id = int(config["id"])
        models.append(
            {
                "id": model_id,
                "connection_id": connection_id,
                "model_id": config["model_name"],
                "display_name": config.get("name") or config["model_name"],
                "source": "MANUAL",
                "supports_chat": role == "chat",
                "max_input_tokens": config.get("max_input_tokens"),
                "supports_image_input": (
                    role == "chat" and bool(config.get("supports_image_input"))
                ),
                "supports_tools": bool(config.get("supports_tools", False)),
                "supports_image_generation": role == "image_gen",
                "capabilities_override": {},
                "enabled": True,
                "billing_tier": config.get("billing_tier", "free"),
                "catalog": _catalog_metadata(config),
                "role": role,
            }
        )

    for cfg in chat_configs:
        if cfg.get("is_auto_mode"):
            continue
        add_config(cfg, "chat")
    for cfg in image_configs:
        if cfg.get("is_auto_mode"):
            continue
        add_config(cfg, "image_gen")

    # Each virtual connection is server-only. Callers that serialize these
    # must strip api_key before returning data to clients.
    return connections, models


__all__ = ["materialize_global_model_catalog"]
