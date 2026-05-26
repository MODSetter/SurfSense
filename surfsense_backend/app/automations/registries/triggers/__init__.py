"""Trigger registry."""

from __future__ import annotations

from .store import all_triggers, get_trigger, register_trigger
from .types import TriggerDefinition

__all__ = [
    "TriggerDefinition",
    "all_triggers",
    "get_trigger",
    "register_trigger",
]
