"""Mutable counters and maps for one agent stream."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.streaming.types import ActivityData
from app.tasks.chat.streaming.handlers.tools.activity import ActivitySpec

_TERMINAL_ACTIVITY_STATUSES = {
    "completed",
    "error",
    "cancelled",
    "interrupted",
}


@dataclass
class AgentEventRelayState:
    """Tracks text, canonical activities, tool depth, and tool-call metadata.

    **Task span (`spanId`)** — ``active_span_id`` groups steps and tools for one
    open delegating ``task`` episode. ``active_task_run_id`` is the LangGraph
    ``run_id`` of that ``task`` so the span clears only when that run ends, not
    when child tools end. Open/close uses ``relay.task_span`` helpers.

    Activities are backend-owned full snapshots. Tool calls only retain the
    opaque ``activityId`` needed to trace a result card to its journal row.
    """

    accumulated_text: str = ""
    current_text_id: str | None = None
    activity_counter: int = 0
    activity_id_by_run: dict[str, str] = field(default_factory=dict)
    activity_snapshot_by_id: dict[str, ActivityData] = field(default_factory=dict)
    activity_spec_by_id: dict[str, ActivitySpec] = field(default_factory=dict)
    resumable_activity_ids_by_kind: dict[str, list[str]] = field(default_factory=dict)
    open_phase_by_scope: dict[str, tuple[str, str]] = field(default_factory=dict)
    terminal_activity_ids: set[str] = field(default_factory=set)
    active_tool_depth: int = 0
    current_reasoning_id: str | None = None
    pending_tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)
    lc_tool_call_id_by_run: dict[str, str] = field(default_factory=dict)
    file_path_by_run: dict[str, str] = field(default_factory=dict)
    index_to_meta: dict[int, dict[str, str]] = field(default_factory=dict)
    ui_tool_call_id_by_run: dict[str, str] = field(default_factory=dict)
    current_lc_tool_call_id: dict[str, str | None] = field(
        default_factory=lambda: {"value": None}
    )
    # Open ``task`` delegation span (one id shared by nested activity); unset outside.
    active_span_id: str | None = None
    active_task_run_id: str | None = None
    active_subagent_type: str | None = None
    deliverable_needs_repair: bool = False
    # Span id minted when a ``task`` tool_call_chunk registers (before ``on_tool_start``).
    pending_task_span_by_lc: dict[str, str] = field(default_factory=dict)

    def span_metadata_if_active(self) -> dict[str, Any] | None:
        """``{"spanId": ...}`` when a span is active; ``None`` otherwise."""
        if self.active_span_id:
            return {"spanId": self.active_span_id}
        return None

    def tool_activity_metadata(
        self, *, activity_id: str | None
    ) -> dict[str, Any] | None:
        """Build ``metadata`` for tool SSE and ``tool-call`` persistence.

        Contract (keys omitted when not applicable):

        - ``spanId`` (str): present while a task-delegation span is active
          (same value as ``span_metadata_if_active()``).
        - ``activityId`` (str): canonical activity snapshot id for this tool.

        Returns ``None`` if neither applies. Whitespace-only
        ``activity_id`` is ignored.
        """
        out: dict[str, Any] = {}
        if self.active_span_id:
            out["spanId"] = self.active_span_id
        if self.active_subagent_type:
            out["context"] = {"subagentType": self.active_subagent_type}
        aid = (activity_id or "").strip()
        if aid:
            out["activityId"] = aid
        return out if out else None

    @classmethod
    def for_invocation(
        cls,
        *,
        initial_activities: list[ActivityData] | None = None,
    ) -> AgentEventRelayState:
        snapshots = {
            activity["id"]: activity
            for activity in initial_activities or []
            if activity.get("status") == "awaiting_approval"
        }
        resumable: dict[str, list[str]] = {}
        for activity in sorted(
            snapshots.values(), key=lambda item: (item["sequence"], item["id"])
        ):
            resumable.setdefault(activity["kind"], []).append(activity["id"])
        return cls(
            activity_counter=max(
                (activity["sequence"] for activity in snapshots.values()), default=0
            ),
            activity_snapshot_by_id=snapshots,
            resumable_activity_ids_by_kind=resumable,
        )

    def next_activity_id(self, step_prefix: str) -> str:
        self.activity_counter += 1
        return f"act_{step_prefix}_{self.activity_counter}"

    def transition_activity(
        self,
        activity_id: str,
        *,
        status: str,
        completed_at: str | None = None,
        details: list[str] | None = None,
    ) -> ActivityData | None:
        current = self.activity_snapshot_by_id.get(activity_id)
        spec = self.activity_spec_by_id.get(activity_id)
        if current is None or spec is None:
            return None
        if activity_id in self.terminal_activity_ids:
            return current
        started_at = current["startedAt"]
        integration = current.get("integration")
        snapshot = spec.snapshot(
            activity_id=activity_id,
            sequence=current["sequence"],
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            completed_at=completed_at,
            details=details if details is not None else current.get("details"),
            integration=integration,
        )
        self.activity_snapshot_by_id[activity_id] = snapshot
        if status in _TERMINAL_ACTIVITY_STATUSES:
            self.terminal_activity_ids.add(activity_id)
            for scope, (_, open_id) in list(self.open_phase_by_scope.items()):
                if open_id == activity_id:
                    self.open_phase_by_scope.pop(scope, None)
        return snapshot
