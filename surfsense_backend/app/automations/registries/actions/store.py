"""Action registry: in-memory dict + ``register_action`` API."""

from __future__ import annotations

from .types import ActionDefinition

_REGISTRY: dict[str, ActionDefinition] = {}


def register_action(action: ActionDefinition) -> None:
    """Add an action to the in-memory registry.

    Raises ``ValueError`` on duplicate ``type`` — registration runs
    once per process, so a duplicate is always a bug.
    """

    if action.type in _REGISTRY:
        raise ValueError(
            f"Action already registered: {action.type!r}"
        )
    _REGISTRY[action.type] = action


def get_action(action_type: str) -> ActionDefinition | None:
    """Look up one action by type. Returns ``None`` on miss."""

    return _REGISTRY.get(action_type)


def all_actions() -> dict[str, ActionDefinition]:
    """Snapshot of the registry as a defensive copy."""

    return dict(_REGISTRY)
