"""A tool as a source lists it, whatever kind of plugin the source is."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceTool:
    name: str
    title: str | None
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any] = field(default_factory=dict)
