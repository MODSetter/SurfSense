"""Backend-owned user-facing presentation for streamed tool activity."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from app.services.streaming.types import (
    ActivityCategory,
    ActivityData,
    ActivityIntegration,
    ActivityStatus,
)

ActivityVisibility = Literal["show", "hide"]
ActivityLifecycle = Literal["invocation", "phase"]


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
        details: list[str] | None = None,
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
        if details:
            snapshot["details"] = details[:5]
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


_ACTIVITY_SPECS: dict[str, ActivitySpec] = {
    "read_file": _copy("Reading file", "Read file", "file", icon_key="file-text"),
    "write_file": _copy("Creating file", "Created file", "file", icon_key="file-plus"),
    "edit_file": _copy("Editing file", "Edited file", "file", icon_key="file-pen"),
    "move_file": _copy("Moving file", "Moved file", "file", icon_key="files"),
    "rm": _copy("Deleting file", "Deleted file", "file", icon_key="file-x"),
    "mkdir": _copy("Creating folder", "Created folder", "file", icon_key="folder-plus"),
    "rmdir": _copy("Deleting folder", "Deleted folder", "file", icon_key="folder-x"),
    "ls": _copy("Reviewing folder", "Reviewed folder", "file", icon_key="folder-open"),
    "list_tree": _copy(
        "Reviewing file tree", "Reviewed file tree", "file", icon_key="folder-tree"
    ),
    "glob": _copy("Finding files", "Found files", "file", icon_key="folder-search"),
    "grep": _copy(
        "Searching project", "Searched project", "file", icon_key="search-code"
    ),
    "execute": _copy("Running command", "Ran command", "action", icon_key="terminal"),
    "execute_code": _copy("Running code", "Ran code", "action", icon_key="square-code"),
    "write_todos": _copy(
        "Planning work",
        "Planned work",
        "action",
        lifecycle="phase",
        icon_key="list-todo",
    ),
    "load_artifact_source": _copy(
        "Opening the artifact",
        "Opened the artifact",
        "artifact",
        lifecycle="phase",
        icon_key="file-input",
    ),
    "read_sandbox_file": _copy(
        "Reviewing the artifact",
        "Reviewed the artifact",
        "artifact",
        lifecycle="phase",
        icon_key="file-text",
    ),
    "load_artifact_instructions": _copy(
        "Loading artifact instructions",
        "Loaded artifact instructions",
        "artifact",
        "hide",
        icon_key="file-input",
    ),
    "verify_artifact": _copy(
        "Checking the artifact",
        "Checked the artifact",
        "artifact",
        icon_key="badge-check",
    ),
    "save_artifact": _copy(
        "Preparing the file", "Presented file", "artifact", icon_key="file-output"
    ),
    "save_document": _copy(
        "Preparing the document",
        "Presented document",
        "artifact",
        icon_key="file-output",
    ),
    "generate_image": _copy(
        "Creating an image", "Created an image", "artifact", icon_key="image"
    ),
    "display_image": _copy(
        "Preparing the image", "Presented image", "artifact", icon_key="image"
    ),
    "generate_podcast": _copy(
        "Creating the podcast", "Created the podcast", "artifact", icon_key="microphone"
    ),
    "generate_video_presentation": _copy(
        "Creating the presentation",
        "Created the presentation",
        "artifact",
        icon_key="film",
    ),
    "search_knowledge_base": _copy(
        "Searching your sources",
        "Searched your sources",
        "research",
        icon_key="library",
    ),
    "ask_knowledge_base": _copy(
        "Reviewing your sources",
        "Reviewed your sources",
        "research",
        icon_key="library",
    ),
    "scrape_webpage": _copy(
        "Reviewing a webpage",
        "Reviewed a webpage",
        "research",
        lifecycle="phase",
        icon_key="scan-text",
    ),
    "google_search.scrape": _copy(
        "Searching the web",
        "Searched the web",
        "research",
        icon_key="search",
        integration_key="google_search",
    ),
    "web.crawl": _copy(
        "Reviewing the web",
        "Reviewed the web",
        "research",
        icon_key="scan-text",
        integration_key="web",
    ),
    "amazon.scrape": _copy(
        "Searching Amazon",
        "Searched Amazon",
        "research",
        icon_key="search",
        integration_key="amazon",
    ),
    "walmart.scrape": _copy(
        "Searching Walmart",
        "Searched Walmart",
        "research",
        icon_key="search",
        integration_key="walmart",
    ),
    "walmart.reviews": _copy(
        "Reviewing Walmart feedback",
        "Reviewed Walmart feedback",
        "research",
        icon_key="search",
        integration_key="walmart",
    ),
    "google_maps.scrape": _copy(
        "Searching Google Maps",
        "Searched Google Maps",
        "research",
        icon_key="search",
        integration_key="google_maps",
    ),
    "google_maps.reviews": _copy(
        "Reviewing Google Maps feedback",
        "Reviewed Google Maps feedback",
        "research",
        icon_key="search",
        integration_key="google_maps",
    ),
    "indeed.scrape": _copy(
        "Searching Indeed",
        "Searched Indeed",
        "research",
        icon_key="search",
        integration_key="indeed",
    ),
    "youtube.scrape": _copy(
        "Searching YouTube",
        "Searched YouTube",
        "research",
        icon_key="search",
        integration_key="youtube",
    ),
    "youtube.comments": _copy(
        "Reviewing YouTube comments",
        "Reviewed YouTube comments",
        "research",
        icon_key="search",
        integration_key="youtube",
    ),
    "reddit.scrape": _copy(
        "Searching Reddit",
        "Searched Reddit",
        "research",
        icon_key="search",
        integration_key="reddit",
    ),
    "tiktok.scrape": _copy(
        "Searching TikTok",
        "Searched TikTok",
        "research",
        icon_key="search",
        integration_key="tiktok",
    ),
    "tiktok.comments": _copy(
        "Reviewing TikTok comments",
        "Reviewed TikTok comments",
        "research",
        icon_key="search",
        integration_key="tiktok",
    ),
    "tiktok.trending": _copy(
        "Reviewing TikTok trends",
        "Reviewed TikTok trends",
        "research",
        icon_key="search",
        integration_key="tiktok",
    ),
    "tiktok.user_search": _copy(
        "Searching TikTok",
        "Searched TikTok",
        "research",
        icon_key="search",
        integration_key="tiktok",
    ),
    "instagram.scrape": _copy(
        "Searching Instagram",
        "Searched Instagram",
        "research",
        icon_key="search",
        integration_key="instagram",
    ),
    "instagram.details": _copy(
        "Reviewing Instagram",
        "Reviewed Instagram",
        "research",
        icon_key="search",
        integration_key="instagram",
    ),
    "link_preview": _copy(
        "Reviewing a link",
        "Reviewed a link",
        "research",
        lifecycle="phase",
        icon_key="external-link",
    ),
    "multi_link_preview": _copy(
        "Reviewing links",
        "Reviewed links",
        "research",
        lifecycle="phase",
        icon_key="external-link",
    ),
    "create_calendar_event": _copy(
        "Creating calendar event",
        "Created calendar event",
        "connector",
        icon_key="calendar",
        integration_key="google_calendar",
    ),
    "update_calendar_event": _copy(
        "Updating calendar event",
        "Updated calendar event",
        "connector",
        icon_key="calendar",
        integration_key="google_calendar",
    ),
    "delete_calendar_event": _copy(
        "Deleting calendar event",
        "Deleted calendar event",
        "connector",
        icon_key="calendar",
        integration_key="google_calendar",
    ),
    "search_calendar_events": _copy(
        "Searching calendar",
        "Searched calendar",
        "connector",
        icon_key="calendar",
        integration_key="google_calendar",
    ),
    "create_automation": _copy(
        "Creating automation", "Created automation", "action", icon_key="workflow"
    ),
    "update_memory": _copy(
        "Remembering preference", "Remembered preference", "action", icon_key="brain"
    ),
    "task": _copy(
        "Working with a specialist",
        "Worked with a specialist",
        "action",
        "hide",
        icon_key="route",
    ),
    "get_connected_accounts": _copy(
        "Checking connected apps",
        "Checked connected apps",
        "connector",
        lifecycle="phase",
        icon_key="search",
    ),
    "generate_report": _copy(
        "Creating report", "Created report", "artifact", "hide", icon_key="file-text"
    ),
    "generate_resume": _copy(
        "Creating resume", "Created resume", "artifact", "hide", icon_key="file-text"
    ),
    "pwd": _copy(
        "Checking folder", "Checked folder", "file", "hide", icon_key="terminal"
    ),
    "cd": _copy(
        "Changing folder", "Changed folder", "file", "hide", icon_key="terminal"
    ),
    "noop": _copy("Working", "Worked", "action", "hide", icon_key="tool"),
    "invalid_tool": _copy(
        "Repairing action", "Repaired action", "action", "hide", icon_key="tool"
    ),
}


def _fallback() -> ActivitySpec:
    # Never derive presentation copy from an unknown model-selected tool name.
    return _copy("Using a tool", "Completed an action", "action", icon_key="tool")


def _with_kind(spec: ActivitySpec, kind: str) -> ActivitySpec:
    return replace(
        spec,
        kind=kind,
        phase_key=kind if spec.lifecycle == "phase" else None,
    )


def resolve_tool_activity(
    tool_name: str,
    *,
    subagent_type: str | None,
    artifact_type: str | None = None,
    repairing_artifact: bool = False,
    trusted_descriptor: dict[str, Any] | None = None,
) -> ActivitySpec:
    """Resolve display semantics from trusted runtime context, never model copy."""
    del artifact_type
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

    explicit = _ACTIVITY_SPECS.get(tool_name)
    if explicit:
        return _with_kind(explicit, tool_name)

    # Dynamic connector/MCP descriptors are backend-authored tool metadata.
    # Require complete, bounded copy; otherwise use the generic safe fallback.
    if isinstance(trusted_descriptor, dict):
        active = trusted_descriptor.get("active_title")
        completed = trusted_descriptor.get("completed_title")
        category = trusted_descriptor.get("category")
        icon_key = trusted_descriptor.get("icon_key")
        if (
            isinstance(active, str)
            and 0 < len(active.strip()) <= 120
            and isinstance(completed, str)
            and 0 < len(completed.strip()) <= 120
            and category in {"file", "research", "artifact", "connector", "action"}
            and isinstance(icon_key, str)
            and 0 < len(icon_key.strip()) <= 64
        ):
            return _with_kind(
                _copy(
                    active.strip(),
                    completed.strip(),
                    category,
                    icon_key=icon_key.strip(),
                ),
                str(trusted_descriptor.get("kind") or "connector.action"),
            )
    return _with_kind(_fallback(), "tool.action")
