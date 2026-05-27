"""``manual`` trigger: fired by a user clicking ``Run now``."""

from __future__ import annotations

from .dispatch import dispatch_manual_run
from .params import ManualTriggerParams

__all__ = ["ManualTriggerParams", "dispatch_manual_run"]

# Side-effect: register on the triggers store.
from . import definition  # noqa: E402, F401
