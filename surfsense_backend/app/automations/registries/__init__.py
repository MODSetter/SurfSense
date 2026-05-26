"""Capability, action, and trigger registries — populated at process startup."""

from __future__ import annotations

from .actions import (
    ActionDefinition,
    ActionHandler,
    all_actions,
    get_action,
    register_action,
)
from .capabilities import (
    Capability,
    CapabilityHandler,
    all_capabilities,
    get_capability,
    register_capability,
)
from .triggers import (
    TriggerDefinition,
    all_triggers,
    get_trigger,
    register_trigger,
)

__all__ = [
    "ActionDefinition",
    "ActionHandler",
    "Capability",
    "CapabilityHandler",
    "TriggerDefinition",
    "all_actions",
    "all_capabilities",
    "all_triggers",
    "get_action",
    "get_capability",
    "get_trigger",
    "register_action",
    "register_capability",
    "register_trigger",
]
