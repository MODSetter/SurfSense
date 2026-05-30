"""Generic dispatch primitives shared across trigger types."""

from __future__ import annotations

from .errors import DispatchError
from .launch import launch_run

__all__ = ["DispatchError", "launch_run"]
