"""Automation lifecycle status."""

from __future__ import annotations

from enum import StrEnum


class AutomationStatus(StrEnum):
    ACTIVE = "active"  # eligible to fire
    PAUSED = "paused"  # kept, but triggers don't fire
    ARCHIVED = "archived"  # read-only history
