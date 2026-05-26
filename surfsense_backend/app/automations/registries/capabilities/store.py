"""Capability registry: in-memory dict + ``register_capability`` API."""

from __future__ import annotations

from .types import Capability

_REGISTRY: dict[str, Capability] = {}


def register_capability(capability: Capability) -> None:
    """Add a capability to the in-memory registry.

    Raises ``ValueError`` on duplicate ``id`` — registration is
    idempotent only at the module level (a module's
    ``register_capability`` call runs once per process), so a
    duplicate is always a bug.
    """

    if capability.id in _REGISTRY:
        raise ValueError(
            f"Capability already registered: {capability.id!r}"
        )
    _REGISTRY[capability.id] = capability


def get_capability(capability_id: str) -> Capability | None:
    """Look up one capability by id. Returns ``None`` on miss."""

    return _REGISTRY.get(capability_id)


def all_capabilities() -> dict[str, Capability]:
    """Snapshot of the registry as a defensive copy.

    Returned dict is safe to iterate while other code calls
    ``register_capability`` (which v1 never does post-startup, but
    the contract holds anyway).
    """

    return dict(_REGISTRY)
