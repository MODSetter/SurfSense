"""``Capability`` dataclass and handler signature. Locked at five fields for v1."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

CapabilityHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class Capability:
    id: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: CapabilityHandler
