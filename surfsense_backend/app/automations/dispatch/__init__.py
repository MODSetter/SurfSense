"""Generic dispatch primitives shared across trigger types."""

from __future__ import annotations

from .errors import DispatchError
from .run import dispatch_run
from .start import start_run

__all__ = ["DispatchError", "dispatch_run", "start_run"]
