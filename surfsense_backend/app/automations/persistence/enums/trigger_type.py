"""Trigger-kind discriminator. v1: schedule | manual; webhook/event in Phase 2/3."""

from __future__ import annotations

from enum import StrEnum


class TriggerType(StrEnum):
    SCHEDULE = "schedule"
    MANUAL = "manual"
