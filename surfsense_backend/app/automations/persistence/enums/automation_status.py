"""``AutomationStatus`` — lifecycle of a stored automation definition."""

from __future__ import annotations

from enum import StrEnum


class AutomationStatus(StrEnum):
    """Status of an automation in the registry.

    ``active``   — eligible to fire from its triggers.
    ``paused``   — definition retained, triggers do not fire.
    ``archived`` — kept for run history only; no edits, no fires.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
