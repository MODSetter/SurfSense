"""``TriggerDefinition`` dataclass. Declarative; firing is the dispatcher's job."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TriggerDefinition:
    type: str
    description: str
    params_schema: dict[str, Any]
    payload_schema: dict[str, Any]
