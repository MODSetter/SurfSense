"""Backend-owned user-facing presentation for streamed tool activity."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Literal

from app.capabilities.core import get_capability
from app.capabilities.core.types import ActivityDescriptor
from app.services.streaming.types import (
    ActivityCategory,
    ActivityData,
    ActivityIntegration,
    ActivityStatus,
)

ActivityVisibility = Literal["show", "hide"]
ActivityLifecycle = Literal["invocation", "phase"]
_ACTIVITY_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ActivitySpec:
    kind: str
    active_title: str
    completed_title: str
    failed_title: str
    cancelled_title: str
    approval_title: str
    interrupted_title: str
    category: ActivityCategory
    icon_key: str
    integration_key: str | None = None
    visibility: ActivityVisibility = "show"
    lifecycle: ActivityLifecycle = "invocation"
    phase_key: str | None = None

    def title_for(self, status: ActivityStatus) -> str:
        return {
            "running": self.active_title,
            "awaiting_approval": self.approval_title,
            "completed": self.completed_title,
            "error": self.failed_title,
            "cancelled": self.cancelled_title,
            "interrupted": self.interrupted_title,
        }[status]

    def snapshot(
        self,
        *,
        activity_id: str,
        sequence: int,
        status: ActivityStatus,
        started_at: str,
        completed_at: str | None = None,
        progress_title: str | None = None,
        integration: ActivityIntegration | None = None,
    ) -> ActivityData:
        snapshot: ActivityData = {
            "id": activity_id,
            "sequence": sequence,
            "kind": self.kind,
            "status": status,
            "title": self.title_for(status),
            "category": self.category,
            "iconKey": self.icon_key,
            "startedAt": started_at,
        }
        if progress_title and status in {"running", "awaiting_approval"}:
            snapshot["progressTitle"] = progress_title
        if completed_at:
            snapshot["completedAt"] = completed_at
        resolved_integration = integration
        if resolved_integration is None and self.integration_key:
            resolved_integration = {
                "source": "native",
                "key": self.integration_key,
            }
        if resolved_integration:
            snapshot["integration"] = resolved_integration
        return snapshot


def _copy(
    active: str,
    completed: str,
    category: ActivityCategory,
    visibility: ActivityVisibility = "show",
    *,
    lifecycle: ActivityLifecycle | None = None,
    icon_key: str | None = None,
    integration_key: str | None = None,
) -> ActivitySpec:
    return ActivitySpec(
        kind="",
        active_title=active,
        completed_title=completed,
        failed_title=f"Couldn't complete: {active}",
        cancelled_title=f"Stopped: {active}",
        approval_title=f"Approval needed: {active}",
        interrupted_title=f"Interrupted: {active}",
        category=category,
        icon_key=icon_key or category,
        integration_key=integration_key,
        visibility=visibility,
        lifecycle=lifecycle or "invocation",
        phase_key="" if lifecycle == "phase" else None,
    )


_INTERNAL_TOOL_NAMES = frozenset(
    {
        "cd",
        "invalid_tool",
        "load_artifact_instructions",
        "noop",
        "pwd",
        "task",
    }
)


def _fallback() -> ActivitySpec:
    # Never derive presentation copy from an unknown model-selected tool name.
    return _copy("Using a tool", "Completed an action", "action", icon_key="tool")


def _with_kind(spec: ActivitySpec, kind: str) -> ActivitySpec:
    return replace(
        spec,
        kind=kind,
        phase_key=kind if spec.lifecycle == "phase" else None,
    )


def _activity_from_descriptor(value: object) -> ActivitySpec | None:
    descriptor = ActivityDescriptor.from_metadata(value)
    if descriptor is None:
        return None
    kind = descriptor.kind
    if kind is None or not _ACTIVITY_KIND_RE.fullmatch(kind):
        kind = "connector.action"
    return _with_kind(
        _copy(
            descriptor.active_title,
            descriptor.completed_title,
            descriptor.category,
            descriptor.visibility,
            lifecycle=descriptor.lifecycle,
            icon_key=descriptor.icon_key,
            integration_key=descriptor.integration_key,
        ),
        kind,
    )


def resolve_tool_activity(
    tool_name: str,
    *,
    subagent_type: str | None,
    repairing_artifact: bool = False,
    trusted_descriptor: dict[str, Any] | None = None,
) -> ActivitySpec:
    """Resolve display semantics from trusted runtime context, never model copy."""
    if tool_name == "execute" and subagent_type == "deliverables":
        return _with_kind(
            _copy(
                "Repairing the artifact"
                if repairing_artifact
                else "Creating the artifact",
                "Repaired the artifact"
                if repairing_artifact
                else "Created the artifact",
                "artifact",
                lifecycle="phase",
                icon_key="terminal",
            ),
            "artifact.repair" if repairing_artifact else "artifact.create",
        )

    # StructuredTool metadata is backend-authored and takes precedence over
    # model-visible names, which can collide across native and MCP tools.
    described = _activity_from_descriptor(trusted_descriptor)
    if described is not None:
        return described

    if tool_name in _INTERNAL_TOOL_NAMES:
        return _with_kind(
            _copy("Using a tool", "Completed an action", "action", "hide"),
            "tool.action",
        )

    try:
        capability = get_capability(tool_name)
    except KeyError:
        capability = None
    if capability is not None and capability.activity is not None:
        described = _activity_from_descriptor(
            capability.activity.as_metadata(kind=capability.name)
        )
        if described is not None:
            return described
    return _with_kind(_fallback(), "tool.action")
