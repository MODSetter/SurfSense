"""Schemas for the automation definition and per-type configs."""

from __future__ import annotations

from .actions import AgentTaskActionParams
from .definition import (
    AutomationDefinition,
    Execution,
    Inputs,
    Metadata,
    PlanStep,
    TriggerSpec,
)
from .triggers import ManualTriggerParams, ScheduleTriggerParams

__all__ = [
    "AgentTaskActionParams",
    "AutomationDefinition",
    "Execution",
    "Inputs",
    "ManualTriggerParams",
    "Metadata",
    "PlanStep",
    "ScheduleTriggerParams",
    "TriggerSpec",
]
