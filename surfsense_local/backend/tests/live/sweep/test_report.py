"""The ETA counts the lanes that were actually busy, since the RAM guard may hold the sweep under its --lanes."""

import pytest

from tests.live.sweep.attempt import Attempt
from tests.live.sweep.report import progress

pytestmark = pytest.mark.unit

NOW = 100_000.0


def _row(status: str, level: str | None, minutes: float = 0.0) -> dict:
    return {"status": status, "level": level, "minutes": minutes, "cost": 0.1}


def test_the_eta_runs_at_the_lanes_busy_so_far_not_the_lanes_asked_for() -> None:
    """Six lanes asked for, but 90 lane-minutes in the last hour is 1.5 lanes busy."""
    rows = [_row("done", "agent", 6.0), _row("done", "below", 6.0)] + [
        _row("pending", None)
    ] * 3
    status = {"pid": None, "lanes": 6, "budget": 200.0, "started": NOW - 3600}
    attempts = [
        Attempt("m", "smoke", n, "passed", minutes=15.0, ended=NOW - 60)
        for n in range(6)
    ]

    shown = progress({"models": rows, "spent": 0.2}, status, attempts, NOW)

    assert shown.busy_lanes == pytest.approx(1.5)
    assert shown.eta_minutes == pytest.approx(3 * 6.0 / 1.5)
    assert "ETA: 0.2 h at 1.5 lanes (as busy as so far)" in shown.text()


def test_in_the_first_ten_minutes_the_eta_uses_the_lanes_asked_for() -> None:
    """Too little has ended yet to say how busy the lanes are."""
    rows = [_row("done", "agent", 6.0), _row("pending", None)]
    status = {"pid": None, "lanes": 6, "started": NOW - 120}

    shown = progress({"models": rows, "spent": 0.1}, status, [], NOW)

    assert shown.busy_lanes is None
    assert shown.eta_minutes == pytest.approx(1.0)
