"""Per-trigger config schemas: one file per trigger type registered in v1."""

from __future__ import annotations

from .manual import ManualTriggerConfig
from .schedule import ScheduleTriggerConfig

__all__ = [
    "ManualTriggerConfig",
    "ScheduleTriggerConfig",
]
