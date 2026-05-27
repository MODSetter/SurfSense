"""Per-trigger params schemas, one per trigger type."""

from __future__ import annotations

from .manual import ManualTriggerParams
from .schedule import ScheduleTriggerParams

__all__ = [
    "ManualTriggerParams",
    "ScheduleTriggerParams",
]
