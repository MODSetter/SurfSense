"""Capability registry."""

from __future__ import annotations

from .store import all_capabilities, get_capability, register_capability
from .types import Capability, CapabilityHandler

__all__ = [
    "Capability",
    "CapabilityHandler",
    "all_capabilities",
    "get_capability",
    "register_capability",
]
