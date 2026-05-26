"""In-memory action registry. Populated once at process startup."""

from __future__ import annotations

from .types import ActionDefinition

_REGISTRY: dict[str, ActionDefinition] = {}


def register_action(action: ActionDefinition) -> None:
    """Register an action. Raises on duplicate type."""
    if action.type in _REGISTRY:
        raise ValueError(f"Action already registered: {action.type!r}")
    _REGISTRY[action.type] = action


def get_action(action_type: str) -> ActionDefinition | None:
    return _REGISTRY.get(action_type)


def all_actions() -> dict[str, ActionDefinition]:
    """Defensive snapshot of the registry."""
    return dict(_REGISTRY)
