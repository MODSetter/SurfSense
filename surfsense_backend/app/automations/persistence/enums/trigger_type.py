"""Trigger-kind discriminator.

``schedule`` and ``event`` are registered. ``manual`` is reserved in the enum
(mirrors the postgres enum) but is intentionally unregistered pending a redesign
of the "Run now" UX.
"""

from __future__ import annotations

from enum import StrEnum


class TriggerType(StrEnum):
    SCHEDULE = "schedule"
    EVENT = "event"
    MANUAL = "manual"
