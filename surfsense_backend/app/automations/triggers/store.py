"""In-memory trigger registry. Populated once at process startup."""

from __future__ import annotations

from .types import TriggerDefinition

_REGISTRY: dict[str, TriggerDefinition] = {}


def register_trigger(trigger: TriggerDefinition) -> None:
    """Register a trigger. Raises on duplicate type."""
    if trigger.type in _REGISTRY:
        raise ValueError(f"Trigger already registered: {trigger.type!r}")
    _REGISTRY[trigger.type] = trigger


def get_trigger(trigger_type: str) -> TriggerDefinition | None:
    return _REGISTRY.get(trigger_type)


def all_triggers() -> dict[str, TriggerDefinition]:
    """Defensive snapshot of the registry."""
    return dict(_REGISTRY)
