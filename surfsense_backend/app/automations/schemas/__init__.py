"""Pydantic schemas for the automation definition and per-type configs."""

from __future__ import annotations

from .actions import AgentTaskActionConfig
from .definition import (
    AutomationDefinition,
    ExecutionBlock,
    InputsBlock,
    MetadataBlock,
    PlanStep,
    TriggerSpec,
)
from .triggers import ManualTriggerConfig, ScheduleTriggerConfig

__all__ = [
    "AgentTaskActionConfig",
    "AutomationDefinition",
    "ExecutionBlock",
    "InputsBlock",
    "ManualTriggerConfig",
    "MetadataBlock",
    "PlanStep",
    "ScheduleTriggerConfig",
    "TriggerSpec",
]
