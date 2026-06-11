"""Override-aware model capability lookup."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CAPABILITY_FIELDS = {
    "chat": "supports_chat",
    "vision": "supports_image_input",
    "image_gen": "supports_image_generation",
    "tools": "supports_tools",
}


def _get_value(model: Any, key: str) -> Any:
    if isinstance(model, Mapping):
        return model.get(key)
    return getattr(model, key, None)


def has_capability(model: Any, capability: str) -> bool:
    field = CAPABILITY_FIELDS.get(capability)
    if field is None:
        return False

    override = _get_value(model, "capabilities_override") or {}
    if isinstance(override, Mapping) and field in override:
        return bool(override[field])
    if isinstance(override, Mapping) and capability in override:
        return bool(override[capability])

    return bool(_get_value(model, field))


__all__ = ["CAPABILITY_FIELDS", "has_capability"]
