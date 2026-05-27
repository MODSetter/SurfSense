"""Models, one per table."""

from __future__ import annotations

from .automation import Automation
from .run import AutomationRun
from .trigger import AutomationTrigger

__all__ = [
    "Automation",
    "AutomationRun",
    "AutomationTrigger",
]
