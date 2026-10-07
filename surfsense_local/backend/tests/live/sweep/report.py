"""How far the sweep has got (models done, passing, below, spend, ETA), read from its files while it runs or after."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

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

    @property
    def done(self) -> int:
        return self.passing + self.below

    @property
    def left(self) -> int:
        return self.total - self.done - self.unresolved

    @property
    def eta_minutes(self) -> float | None:
        if self.minutes_per_model is None or not self.lanes:
            return None
        return self.left * self.minutes_per_model / self.lanes

    def text(self) -> str:
        budget = f" of ${self.budget:.2f}" if self.budget is not None else ""
        lines = [
            f"runner: {self.runner}",
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
                f"ETA: {self.eta_minutes / 60:.1f} h at {self.lanes} lanes, "
                f"about ${self.spent + self.left * (self.cost_per_model or 0):.2f} in all"
            )
        if self.in_flight:
            lines.append("in flight: " + ", ".join(self.in_flight))
        return "\n".join(lines)


def progress(results: dict[str, Any], status: dict[str, Any]) -> Progress:
    """From sweep-results.json and the runner's status.json."""
    rows = results["models"]
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
    return progress(results, status)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
