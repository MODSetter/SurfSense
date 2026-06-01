"""Triggers domain: registry surface + built-in trigger packages.

Built-in trigger types live under ``builtin/`` and self-register at import time.
"""

from __future__ import annotations

from .store import all_triggers, get_trigger, register_trigger
from .types import TriggerDefinition

__all__ = [
    "TriggerDefinition",
    "all_triggers",
    "get_trigger",
    "register_trigger",
]

# Built-in triggers self-register at import time.
from . import builtin  # noqa: F401
