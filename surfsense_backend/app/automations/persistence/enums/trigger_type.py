"""Trigger-kind discriminator.

v1 only registers ``schedule``. ``manual`` is reserved in the enum (mirrors the
postgres enum) but is intentionally unregistered pending a redesign of the
"Run now" UX.
"""

from __future__ import annotations

from enum import StrEnum


class TriggerType(StrEnum):
    SCHEDULE = "schedule"
    MANUAL = "manual"
