"""Action and trigger registries — populated at process startup."""

from __future__ import annotations

from .actions import (
    ActionContext,
    ActionDefinition,
    ActionHandler,
    ActionHandlerFactory,
    all_actions,
    get_action,
    register_action,
)
from .triggers import (
    TriggerDefinition,
    all_triggers,
    get_trigger,
    register_trigger,
)

__all__ = [
    "ActionContext",
    "ActionDefinition",
    "ActionHandler",
    "ActionHandlerFactory",
    "TriggerDefinition",
    "all_actions",
    "all_triggers",
    "get_action",
    "get_trigger",
    "register_action",
    "register_trigger",
]
