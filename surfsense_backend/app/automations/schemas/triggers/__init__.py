"""Per-trigger config schemas, one per trigger type."""

from __future__ import annotations

from .manual import ManualTriggerConfig
from .schedule import ScheduleTriggerConfig

__all__ = [
    "ManualTriggerConfig",
    "ScheduleTriggerConfig",
]
