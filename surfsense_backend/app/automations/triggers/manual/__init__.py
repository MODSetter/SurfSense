"""``manual`` trigger: fired by a user clicking ``Run now``."""

from __future__ import annotations

from .params import ManualTriggerParams

__all__ = ["ManualTriggerParams"]

# Side-effect: register on the triggers store.
from . import definition  # noqa: E402, F401
