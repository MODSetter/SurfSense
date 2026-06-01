"""Automation definition envelope and its components."""

from __future__ import annotations

from .envelope import AutomationDefinition, AutomationModels
from .execution import Execution
from .inputs import Inputs
from .metadata import Metadata
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec

__all__ = [
    "AutomationDefinition",
    "AutomationModels",
    "Execution",
    "Inputs",
    "Metadata",
    "PlanStep",
    "TriggerSpec",
]
