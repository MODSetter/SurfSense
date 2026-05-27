"""Schemas for the automation definition envelope.

Per-action and per-trigger params schemas live with the action/trigger
implementations (``app.automations.actions.<name>.params`` /
``app.automations.triggers.<name>.params``); only the cross-cutting envelope
lives here.
"""

from __future__ import annotations

from .definition import (
    AutomationDefinition,
    Execution,
    Inputs,
    Metadata,
    PlanStep,
    TriggerSpec,
)

__all__ = [
    "AutomationDefinition",
    "Execution",
    "Inputs",
    "Metadata",
    "PlanStep",
    "TriggerSpec",
]
