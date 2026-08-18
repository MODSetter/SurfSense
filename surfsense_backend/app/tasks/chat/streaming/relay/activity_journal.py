"""Canonical lifecycle owner for one turn's user-visible activities."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.streaming.types import (
    ActivityData,
    ActivityIntegration,
    ActivityStatus,
)
from app.tasks.chat.streaming.handlers.tools.activity import ActivitySpec

_TERMINAL_STATUSES = {"completed", "error", "cancelled", "interrupted"}
_STATUS_SEVERITY: dict[ActivityStatus, int] = {
    "running": 0,
    "awaiting_approval": 0,
    "completed": 1,
    "interrupted": 2,
    "cancelled": 3,
    "error": 4,
}


@dataclass(frozen=True, slots=True)
class ActivityStart:
    activity_id: str | None
    snapshots: tuple[ActivityData, ...] = ()


@dataclass(frozen=True, slots=True)
class ActivityFinish:
    activity_id: str | None
    snapshot: ActivityData | None = None


@dataclass
class ActivityJournal:
    """Own activity identity, phase reuse, resume binding, and transitions."""

    counter: int = 0
    id_by_run: dict[str, str] = field(default_factory=dict)
    snapshot_by_id: dict[str, ActivityData] = field(default_factory=dict)
    spec_by_id: dict[str, ActivitySpec] = field(default_factory=dict)
    open_phase_by_scope: dict[str, tuple[str, str]] = field(default_factory=dict)
    terminal_ids: set[str] = field(default_factory=set)
    resume_id_by_tool_call: dict[str, str] = field(default_factory=dict)
    active_runs_by_activity: dict[str, set[str]] = field(default_factory=dict)
    deferred_close_at_by_activity: dict[str, str] = field(default_factory=dict)
    deferred_outcome_by_activity: dict[str, tuple[ActivityStatus, str]] = field(
        default_factory=dict
    )

    @classmethod
    def resume(
        cls,
        *,
        activities: list[ActivityData] | None = None,
        activity_id_by_tool_call: dict[str, str] | None = None,
    ) -> ActivityJournal:
        snapshots = {
            activity["id"]: activity
            for activity in activities or []
            if activity.get("status") == "awaiting_approval"
        }
        valid_ids = snapshots.keys()
        bindings = {
            tool_call_id: activity_id
            for tool_call_id, activity_id in (activity_id_by_tool_call or {}).items()
            if activity_id in valid_ids
        }
        return cls(
            counter=max(
                (activity["sequence"] for activity in snapshots.values()), default=0
            ),
            snapshot_by_id=snapshots,
            resume_id_by_tool_call=bindings,
        )

    def begin_tool(
        self,
        *,
        spec: ActivitySpec,
        run_id: str,
        step_prefix: str,
        scope: str,
        started_at: str,
        tool_call_id: str,
        langchain_tool_call_id: str | None,
        integration: ActivityIntegration | None,
    ) -> ActivityStart:
        if spec.visibility == "hide":
            return ActivityStart(None)

        emitted: list[ActivityData] = []
        phase_key = spec.phase_key if spec.lifecycle == "phase" else None
        open_phase = self.open_phase_by_scope.get(scope)
        reuse_phase = bool(
            phase_key
            and open_phase
            and open_phase[0] == phase_key
            and open_phase[1] not in self.terminal_ids
        )

        if open_phase and not reuse_phase:
            self.open_phase_by_scope.pop(scope, None)
            closed = self._request_phase_close(
                open_phase[1], status="completed", completed_at=started_at
            )
            if closed is not None:
                emitted.append(closed)

        if reuse_phase and open_phase:
            activity_id = open_phase[1]
            snapshot = self.snapshot_by_id[activity_id]
        else:
            activity_id = self._consume_resume_id(langchain_tool_call_id, tool_call_id)
            if activity_id is None:
                activity_id = self._next_id(step_prefix)
            previous = self.snapshot_by_id.get(activity_id)
            snapshot = spec.snapshot(
                activity_id=activity_id,
                sequence=previous["sequence"] if previous else self.counter,
                status="running",
                started_at=previous["startedAt"] if previous else started_at,
                integration=integration
                or (previous.get("integration") if previous else None),
            )
            self.spec_by_id[activity_id] = spec
            self.snapshot_by_id[activity_id] = snapshot
            if phase_key:
                self.open_phase_by_scope[scope] = (phase_key, activity_id)

        if run_id:
            self.id_by_run[run_id] = activity_id
            self.active_runs_by_activity.setdefault(activity_id, set()).add(run_id)
        emitted.append(snapshot)
        return ActivityStart(activity_id, tuple(emitted))

    def finish_tool(
        self,
        *,
        run_id: str,
        status: ActivityStatus,
        completed_at: str,
    ) -> ActivityFinish:
        activity_id = self.id_by_run.pop(run_id, None) if run_id else None
        if activity_id is None:
            return ActivityFinish(None)
        spec = self.spec_by_id.get(activity_id)
        active_runs = self.active_runs_by_activity.get(activity_id)
        if active_runs is not None:
            active_runs.discard(run_id)
            if not active_runs:
                self.active_runs_by_activity.pop(activity_id, None)
        if spec is None:
            return ActivityFinish(activity_id)
        if spec.lifecycle == "phase":
            if status != "completed":
                self._defer_outcome(activity_id, status, completed_at)
            if activity_id in self.active_runs_by_activity:
                return ActivityFinish(activity_id)
            deferred = self.deferred_outcome_by_activity.pop(activity_id, None)
            close_at = self.deferred_close_at_by_activity.pop(activity_id, None)
            if deferred is not None:
                status, completed_at = deferred
            elif close_at is not None:
                status, completed_at = "completed", close_at
            else:
                return ActivityFinish(activity_id)
        return ActivityFinish(
            activity_id,
            self.transition(
                activity_id,
                status=status,
                completed_at=completed_at,
            ),
        )

    def transition(
        self,
        activity_id: str,
        *,
        status: ActivityStatus,
        completed_at: str | None = None,
        progress_title: str | None = None,
    ) -> ActivityData | None:
        current = self.snapshot_by_id.get(activity_id)
        spec = self.spec_by_id.get(activity_id)
        if current is None or spec is None:
            return None
        if activity_id in self.terminal_ids:
            return current
        snapshot = spec.snapshot(
            activity_id=activity_id,
            sequence=current["sequence"],
            status=status,
            started_at=current["startedAt"],
            completed_at=completed_at,
            progress_title=(
                progress_title
                if progress_title is not None
                else current.get("progressTitle")
            ),
            integration=current.get("integration"),
        )
        self.snapshot_by_id[activity_id] = snapshot
        if status in _TERMINAL_STATUSES:
            self.terminal_ids.add(activity_id)
            for scope, (_, open_id) in list(self.open_phase_by_scope.items()):
                if open_id == activity_id:
                    self.open_phase_by_scope.pop(scope, None)
        return snapshot

    def complete_open_phases(self, *, completed_at: str) -> list[ActivityData]:
        snapshots: list[ActivityData] = []
        for scope, (_, activity_id) in list(self.open_phase_by_scope.items()):
            self.open_phase_by_scope.pop(scope, None)
            snapshot = self._request_phase_close(
                activity_id, status="completed", completed_at=completed_at
            )
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def await_approval(self) -> list[ActivityData]:
        snapshots: list[ActivityData] = []
        for activity_id, current in list(self.snapshot_by_id.items()):
            if current.get("status") not in {"running", "awaiting_approval"}:
                continue
            snapshot = self.transition(activity_id, status="awaiting_approval")
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def interrupt_running(self, *, completed_at: str) -> list[ActivityData]:
        snapshots: list[ActivityData] = []
        for activity_id, current in list(self.snapshot_by_id.items()):
            if current.get("status") != "running":
                continue
            for run_id in self.active_runs_by_activity.pop(activity_id, set()):
                self.id_by_run.pop(run_id, None)
            self.deferred_close_at_by_activity.pop(activity_id, None)
            self.deferred_outcome_by_activity.pop(activity_id, None)
            snapshot = self.transition(
                activity_id,
                status="interrupted",
                completed_at=completed_at,
            )
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def update_current_progress(self, detail: str) -> ActivityData | None:
        candidates = [
            snapshot
            for snapshot in self.snapshot_by_id.values()
            if snapshot.get("status") in {"running", "awaiting_approval"}
        ]
        if not candidates:
            return None
        current = max(candidates, key=lambda snapshot: snapshot["sequence"])
        return self.transition(
            current["id"],
            status=current["status"],
            progress_title=detail,
        )

    def _request_phase_close(
        self,
        activity_id: str,
        *,
        status: ActivityStatus,
        completed_at: str,
    ) -> ActivityData | None:
        if status != "completed":
            self._defer_outcome(activity_id, status, completed_at)
        if activity_id in self.active_runs_by_activity:
            self.deferred_close_at_by_activity.setdefault(activity_id, completed_at)
            return None
        deferred = self.deferred_outcome_by_activity.pop(activity_id, None)
        self.deferred_close_at_by_activity.pop(activity_id, None)
        if deferred is not None:
            status, completed_at = deferred
        return self.transition(activity_id, status=status, completed_at=completed_at)

    def _defer_outcome(
        self,
        activity_id: str,
        status: ActivityStatus,
        completed_at: str,
    ) -> None:
        current = self.deferred_outcome_by_activity.get(activity_id)
        if current is None or _STATUS_SEVERITY[status] > _STATUS_SEVERITY[current[0]]:
            self.deferred_outcome_by_activity[activity_id] = (status, completed_at)

    def _next_id(self, step_prefix: str) -> str:
        self.counter += 1
        return f"act_{step_prefix}_{self.counter}"

    def _consume_resume_id(self, *tool_call_ids: str | None) -> str | None:
        activity_id = next(
            (
                self.resume_id_by_tool_call[tool_call_id]
                for tool_call_id in tool_call_ids
                if tool_call_id and tool_call_id in self.resume_id_by_tool_call
            ),
            None,
        )
        if activity_id is None:
            return None
        for key, value in list(self.resume_id_by_tool_call.items()):
            if value == activity_id:
                self.resume_id_by_tool_call.pop(key, None)
        return activity_id
