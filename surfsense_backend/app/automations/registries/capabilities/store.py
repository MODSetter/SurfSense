"""In-memory capability registry. Populated once at process startup."""

from __future__ import annotations

from .types import Capability

_REGISTRY: dict[str, Capability] = {}


def register_capability(capability: Capability) -> None:
    """Register a capability. Raises on duplicate id."""
    if capability.id in _REGISTRY:
        raise ValueError(f"Capability already registered: {capability.id!r}")
    _REGISTRY[capability.id] = capability


def get_capability(capability_id: str) -> Capability | None:
    return _REGISTRY.get(capability_id)


def all_capabilities() -> dict[str, Capability]:
    """Defensive snapshot of the registry."""
    return dict(_REGISTRY)
