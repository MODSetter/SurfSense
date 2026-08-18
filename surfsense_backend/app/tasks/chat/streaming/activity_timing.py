"""Backend-owned active-time clock for the user-visible activity journal."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns

from app.services.streaming.types import ActivityTimingData, ActivityTimingStatus

_NANOSECONDS_PER_MILLISECOND = 1_000_000


@dataclass
class ActivityTimer:
    """Measure one assistant turn's active wall time.

    The timer starts when the backend accepts a new or resumed turn, includes
    model, tool, retry, and final-answer work, and excludes time suspended for
    human approval.
    """

    active_duration_ns: int
    active_since_ns: int | None
    status: ActivityTimingStatus

    @classmethod
    def start(cls, *, now_ns: int | None = None) -> ActivityTimer:
        return cls(
            active_duration_ns=0,
            active_since_ns=now_ns if now_ns is not None else monotonic_ns(),
            status="running",
        )

    @classmethod
    def resume(
        cls,
        snapshot: ActivityTimingData,
        *,
        now_ns: int | None = None,
    ) -> ActivityTimer:
        if snapshot["status"] != "paused":
            raise ValueError("Only a paused activity timer can resume")
        return cls(
            active_duration_ns=(
                snapshot["activeDurationMs"] * _NANOSECONDS_PER_MILLISECOND
            ),
            active_since_ns=now_ns if now_ns is not None else monotonic_ns(),
            status="running",
        )

    def snapshot(self, *, now_ns: int | None = None) -> ActivityTimingData:
        duration_ns = self.active_duration_ns
        if self.status == "running" and self.active_since_ns is not None:
            observed_ns = now_ns if now_ns is not None else monotonic_ns()
            duration_ns += max(0, observed_ns - self.active_since_ns)
        return {
            "status": self.status,
            "activeDurationMs": duration_ns // _NANOSECONDS_PER_MILLISECOND,
        }

    def pause(self, *, now_ns: int | None = None) -> ActivityTimingData:
        if self.status != "running":
            raise ValueError("Only a running activity timer can pause")
        self._stop_segment(now_ns=now_ns)
        self.status = "paused"
        return self.snapshot()

    def complete(self, *, now_ns: int | None = None) -> ActivityTimingData:
        if self.status != "running":
            raise ValueError("Only a running activity timer can complete")
        self._stop_segment(now_ns=now_ns)
        self.status = "completed"
        return self.snapshot()

    def complete_if_running(
        self, *, now_ns: int | None = None
    ) -> ActivityTimingData | None:
        """Complete cleanup work once without changing paused/terminal timers."""
        if self.status != "running":
            return None
        return self.complete(now_ns=now_ns)

    def _stop_segment(self, *, now_ns: int | None) -> None:
        if self.status != "running" or self.active_since_ns is None:
            return
        stopped_at_ns = now_ns if now_ns is not None else monotonic_ns()
        self.active_duration_ns += max(0, stopped_at_ns - self.active_since_ns)
        self.active_since_ns = None
