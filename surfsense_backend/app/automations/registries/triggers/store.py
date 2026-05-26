"""Trigger registry: in-memory dict + ``register_trigger`` API."""

from __future__ import annotations

from .types import TriggerDefinition

_REGISTRY: dict[str, TriggerDefinition] = {}


def register_trigger(trigger: TriggerDefinition) -> None:
    """Add a trigger to the in-memory registry.

    Raises ``ValueError`` on duplicate ``type`` — registration runs
    once per process, so a duplicate is always a bug.
    """

    if trigger.type in _REGISTRY:
        raise ValueError(
            f"Trigger already registered: {trigger.type!r}"
        )
    _REGISTRY[trigger.type] = trigger


def get_trigger(trigger_type: str) -> TriggerDefinition | None:
    """Look up one trigger by type. Returns ``None`` on miss."""

    return _REGISTRY.get(trigger_type)


def all_triggers() -> dict[str, TriggerDefinition]:
    """Snapshot of the registry as a defensive copy."""

    return dict(_REGISTRY)
