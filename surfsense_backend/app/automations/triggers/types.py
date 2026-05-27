"""``TriggerDefinition`` dataclass. Declarative; firing is the dispatcher's job."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class TriggerDefinition:
    type: str
    description: str
    params_model: type[BaseModel]

    @property
    def params_schema(self) -> dict[str, Any]:
        """JSON Schema (draft 2020-12) derived from ``params_model``."""
        return self.params_model.model_json_schema()
