"""``RunStatus`` — the state machine of a single ``AutomationRun``."""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """Lifecycle states of an ``AutomationRun`` row.

    Transitions are linear with three terminal branches:

        pending → running → (succeeded | failed | cancelled | timed_out)

    ``pending``    — row created, executor task enqueued, work not started.
    ``running``    — executor has picked up the run.
    ``succeeded``  — terminal: plan completed without error.
    ``failed``     — terminal: at least one step raised an unrecoverable error.
    ``cancelled``  — terminal: caller asked for cancellation.
    ``timed_out``  — terminal: run exceeded its configured timeout.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
