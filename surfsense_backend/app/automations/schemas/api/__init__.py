"""Request/response schemas for the automations HTTP layer."""

from __future__ import annotations

from .automation import (
    AutomationCreate,
    AutomationDetail,
    AutomationList,
    AutomationSummary,
    AutomationUpdate,
)
from .run import RunDetail, RunList, RunSummary
from .trigger import TriggerCreate, TriggerDetail, TriggerUpdate

__all__ = [
    "AutomationCreate",
    "AutomationDetail",
    "AutomationList",
    "AutomationSummary",
    "AutomationUpdate",
    "RunDetail",
    "RunList",
    "RunSummary",
    "TriggerCreate",
    "TriggerDetail",
    "TriggerUpdate",
]
