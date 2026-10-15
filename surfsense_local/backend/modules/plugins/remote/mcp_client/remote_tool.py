"""A tool as a plugin's server describes it in `tools/list`."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RemoteTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_listing(cls, listed: dict[str, Any]) -> "RemoteTool":
        return cls(
            name=listed["name"],
            description=listed.get("description") or "",
            input_schema=listed.get("inputSchema") or {"type": "object"},
            title=listed.get("title"),
            annotations=listed.get("annotations") or {},
        )
