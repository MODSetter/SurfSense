"""``ActionDefinition`` dataclass and handler signature."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    type: str
    name: str
    description: str
    config_schema: dict[str, Any]
    handler: ActionHandler
