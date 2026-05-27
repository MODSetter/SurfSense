"""Schemas for the automation definition and per-type configs."""

from __future__ import annotations

from .actions import AgentTaskActionParams
from .definition import (
    AutomationDefinition,
    ExecutionBlock,
    InputsBlock,
    MetadataBlock,
    PlanStep,
    TriggerSpec,
)
from .triggers import ManualTriggerParams, ScheduleTriggerParams

__all__ = [
    "AgentTaskActionParams",
    "AutomationDefinition",
    "ExecutionBlock",
    "InputsBlock",
    "ManualTriggerParams",
    "MetadataBlock",
    "PlanStep",
    "ScheduleTriggerParams",
    "TriggerSpec",
]
