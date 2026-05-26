"""Action registry: ``types.py`` (dataclass), ``store.py`` (dict + register fn)."""

from __future__ import annotations

from .store import all_actions, get_action, register_action
from .types import ActionDefinition, ActionHandler

__all__ = [
    "ActionDefinition",
    "ActionHandler",
    "all_actions",
    "get_action",
    "register_action",
]
