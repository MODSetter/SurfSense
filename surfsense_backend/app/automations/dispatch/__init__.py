"""Public dispatch surface for firing automations."""

from .manual import DispatchError, dispatch_manual_run

__all__ = [
    "DispatchError",
    "dispatch_manual_run",
]
