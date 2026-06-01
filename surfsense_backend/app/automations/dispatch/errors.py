"""Dispatch errors raised when a fire request cannot be turned into a run."""

from __future__ import annotations


class DispatchError(Exception):
    """A dispatch could not proceed (missing trigger, invalid inputs, ...)."""
