"""Identity payload describing which agent produced a stream event."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EmitterLevel = Literal["main", "subagent"]


@dataclass(frozen=True)
class Emitter:
    level: EmitterLevel
    subagent_type: str | None = None
    subagent_run_id: str | None = None
    parent_tool_call_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"level": self.level}
        if self.subagent_type is not None:
            payload["subagent_type"] = self.subagent_type
        if self.subagent_run_id is not None:
            payload["subagent_run_id"] = self.subagent_run_id
        if self.parent_tool_call_id is not None:
            payload["parent_tool_call_id"] = self.parent_tool_call_id
        if self.extra:
            payload.update(self.extra)
        return payload


MAIN_EMITTER = Emitter(level="main")


def main_emitter() -> Emitter:
    return MAIN_EMITTER


def subagent_emitter(
    *,
    subagent_type: str,
    subagent_run_id: str,
    parent_tool_call_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Emitter:
    return Emitter(
        level="subagent",
        subagent_type=subagent_type,
        subagent_run_id=subagent_run_id,
        parent_tool_call_id=parent_tool_call_id,
        extra=dict(extra or {}),
    )


def attach_emitted_by(
    payload: dict[str, Any], emitter: Emitter | None
) -> dict[str, Any]:
    if emitter is None:
        return payload
    payload["emitted_by"] = emitter.to_payload()
    return payload
