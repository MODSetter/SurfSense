"""How far the sweep has got (models done, passing, below, spend, ETA), read from its files while it runs or after."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from tests.live.sweep.attempt import Attempt
from tests.live.sweep.attempt_log import AttemptLog
from tests.live.sweep.results import RESULTS

STATUS = "status.json"


@dataclass(frozen=True)
class Progress:
    total: int
    passing: int
    below: int
    unresolved: int
    started: int
    in_flight: list[str]
    spent: float
    budget: float | None
    lanes: int | None
    # Lane-minutes and dollars per finished model.
    minutes_per_model: float | None
    cost_per_model: float | None
    runner: str
    # Cases running at once on average since the runner started: the RAM guard may hold it under `lanes`.
    busy_lanes: float | None = None
    # Why the last runner stopped before every model had its verdict.
    stopped: str | None = None

    @property
    def done(self) -> int:
        return self.passing + self.below

    @property
    def left(self) -> int:
        return self.total - self.done - self.unresolved

    @property
    def eta_lanes(self) -> float | None:
        return self.busy_lanes or self.lanes

    @property
    def eta_minutes(self) -> float | None:
        if self.minutes_per_model is None or not self.eta_lanes:
            return None
        return self.left * self.minutes_per_model / self.eta_lanes

    def text(self) -> str:
        budget = f" of ${self.budget:.2f}" if self.budget is not None else ""
        lines = [
            f"runner: {self.runner}",
            *([f"stopped: {self.stopped}"] if self.stopped else []),
            f"models: {self.done} done of {self.total} ({self.passing} agent, "
            f"{self.below} below), {self.unresolved} unresolved, "
            f"{self.started} under way, {self.left} left",
            f"spent: ${self.spent:.2f}{budget}",
        ]
        if self.minutes_per_model is not None and self.cost_per_model is not None:
            lines.append(
                f"per finished model: {self.minutes_per_model:.1f} lane-minutes, "
                f"${self.cost_per_model:.3f}"
            )
        if self.eta_minutes is not None:
            lines.append(
                f"ETA: {self.eta_minutes / 60:.1f} h at {self.eta_lanes:.1f} lanes"
                f"{' (as busy as so far)' if self.busy_lanes else ''}, "
                f"about ${self.spent + self.left * (self.cost_per_model or 0):.2f} in all"
            )
        if self.in_flight:
            lines.append("in flight: " + ", ".join(self.in_flight))
        return "\n".join(lines)


def progress(
    results: dict[str, Any],
    status: dict[str, Any],
    attempts: list[Attempt],
    now: float,
) -> Progress:
    """From sweep-results.json, the runner's status.json and attempts.jsonl."""
    rows = [*results["models"], *results.get("unfinished", [])]
    finished = [r for r in rows if r["status"] in ("done", "unresolved")]
    alive = status.get("pid") and psutil.pid_exists(status["pid"])
    running = status.get("running", []) if alive else []
    return Progress(
        total=len(rows),
        passing=sum(r["level"] == "agent" for r in rows),
        below=sum(r["level"] == "below" for r in rows),
        unresolved=sum(r["status"] == "unresolved" for r in rows),
        started=sum(r["status"] == "running" for r in rows),
        in_flight=[f"{u['model']} {u['case']} #{u['number']}" for u in running],
        spent=results["spent"],
        budget=status.get("budget"),
        lanes=status.get("lanes"),
        minutes_per_model=_mean([r["minutes"] for r in finished]),
        cost_per_model=_mean([r["cost"] for r in finished]),
        runner=f"running (pid {status['pid']})" if alive else "not running",
        busy_lanes=_busy_lanes(attempts, status.get("started"), now),
        stopped=status.get("stopped"),
    )


def read(out: Path) -> Progress:
    """The sweep's progress from the files under `out`."""
    results = json.loads((out / RESULTS).read_text(encoding="utf-8"))
    status_path = out / STATUS
    status = (
        json.loads(status_path.read_text(encoding="utf-8"))
        if status_path.is_file()
        else {}
    )
    attempts = AttemptLog(out / "attempts.jsonl").read()
    return progress(results, status, attempts, time.time())


def _busy_lanes(
    attempts: list[Attempt], started: float | None, now: float
) -> float | None:
    """Lane-minutes ended since the runner started, over the minutes since; None in its first ten minutes."""
    if not started or now - started < 600:
        return None
    busy = sum(a.minutes for a in attempts if a.ended >= started)
    return busy / ((now - started) / 60) or None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
