"""In-process capability registry, populated at import by each verb's ``definition.py``."""

from __future__ import annotations

from app.capabilities.types import Capability

_REGISTRY: dict[str, Capability] = {}


def register_capability(capability: Capability) -> None:
    """Add (or replace) a verb by name."""
    _REGISTRY[capability.name] = capability


def get_capability(name: str) -> Capability:
    return _REGISTRY[name]


def all_capabilities() -> list[Capability]:
    return list(_REGISTRY.values())
