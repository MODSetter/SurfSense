"""Automation definition envelope and its building blocks."""

from __future__ import annotations

from .envelope import AutomationDefinition
from .execution import ExecutionBlock
from .inputs import InputsBlock
from .metadata import MetadataBlock
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec

__all__ = [
    "AutomationDefinition",
    "ExecutionBlock",
    "InputsBlock",
    "MetadataBlock",
    "PlanStep",
    "TriggerSpec",
]
