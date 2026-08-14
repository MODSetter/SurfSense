"""Backend-owned active-time clock for the user-visible activity journal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.streaming.types import ActivityTimingData, ActivityTimingStatus


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ActivityTimer:
    """Accumulate execution time while excluding HITL suspension."""

    active_duration_ms: int
    active_since: datetime | None
    status: ActivityTimingStatus
    sampled_at: datetime

    @classmethod
    def start(cls, *, now: datetime | None = None) -> ActivityTimer:
        started_at = now or _now()
        return cls(
            active_duration_ms=0,
            active_since=started_at,
            status="running",
            sampled_at=started_at,
        )

    @classmethod
    def resume(
        cls,
        snapshot: ActivityTimingData,
        *,
        now: datetime | None = None,
    ) -> ActivityTimer:
        if snapshot["status"] != "paused":
            raise ValueError("Only a paused activity timer can resume")
        resumed_at = now or _now()
        return cls(
            active_duration_ms=snapshot["activeDurationMs"],
            active_since=resumed_at,
            status="running",
            sampled_at=resumed_at,
        )

    def snapshot(self, *, now: datetime | None = None) -> ActivityTimingData:
        duration = self.active_duration_ms
        sampled_at = self.sampled_at
        if self.status == "running" and self.active_since is not None:
            sampled_at = now or _now()
            duration += max(
                0,
                int((sampled_at - self.active_since).total_seconds() * 1000),
            )
        return {
            "status": self.status,
            "activeDurationMs": duration,
            "sampledAt": sampled_at.isoformat(),
        }

    def pause(self, *, now: datetime | None = None) -> ActivityTimingData:
        if self.status != "running":
            raise ValueError("Only a running activity timer can pause")
        self._stop_segment(now=now)
        self.status = "paused"
        return self.snapshot()

    def complete(self, *, now: datetime | None = None) -> ActivityTimingData:
        if self.status != "running":
            raise ValueError("Only a running activity timer can complete")
        self._stop_segment(now=now)
        self.status = "completed"
        return self.snapshot()

    def _stop_segment(self, *, now: datetime | None) -> None:
        if self.status != "running" or self.active_since is None:
            return
        stopped_at = now or _now()
        self.active_duration_ms += max(
            0,
            int((stopped_at - self.active_since).total_seconds() * 1000),
        )
        self.active_since = None
        self.sampled_at = stopped_at
