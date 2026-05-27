"""``schedule`` trigger: fired on a cron schedule in a given timezone."""

from __future__ import annotations

from .params import ScheduleTriggerParams

__all__ = ["ScheduleTriggerParams"]

# Side-effect: register on the triggers store.
from . import definition  # noqa: E402, F401
