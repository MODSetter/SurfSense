"""What a model runs next and its verdict: smoke first, uncounted retries, one re-run of a split, unresolved cases."""

import pytest

from tests.live.sweep.attempt import Attempt
from tests.live.sweep.plan import RETRY_AFTER_SECONDS, Next, plan, rolls

pytestmark = pytest.mark.unit


def _cell(case: str, *outcomes: str, ended: float = 100.0) -> list[Attempt]:
    return [
        Attempt("m/x", case, n, outcome, reason=f"{case} {outcome}", ended=ended)  # type: ignore[arg-type]
        for n, outcome in enumerate(outcomes, 1)
    ]


def _plan(in_flight: frozenset[str] = frozenset(), **cells: list[str]):
    by_case = {
        case.replace("_", "-"): _cell(case.replace("_", "-"), *o)
        for case, o in cells.items()
    }
    return plan(by_case, set(in_flight))


def test_a_new_model_runs_smoke_first_and_only_smoke() -> None:
    """Nothing else starts before smoke has passed."""
    made = _plan()

    assert made.next == [Next("smoke")]
    assert made.verdict is None


def test_a_smoke_in_flight_is_not_started_twice() -> None:
    """A case in flight is never started again beside itself."""
    assert _plan(frozenset({"smoke"})).next == []


def test_after_smoke_both_cases_start_together() -> None:
    """The PDF brief and the board pack may run at once in two lanes."""
    made = _plan(smoke=["passed"])

    assert [n.case for n in made.next] == ["pdf-brief", "board-pack"]


def test_a_smoke_the_model_fails_stops_it_at_none_of_two() -> None:
    """Recorded as tested: 0 passed, 2 counted, neither case run."""
    made = _plan(smoke=["failed"])

    assert made.next == []
    verdict = made.verdict
    assert verdict is not None
    assert (verdict.level, verdict.passed, verdict.counted, verdict.run) == (
        "below",
        0,
        2,
        0,
    )
    assert verdict.cells == {
        "smoke": "fail",
        "pdf-brief": "not_run",
        "board-pack": "not_run",
    }
    assert "smoke failed" in verdict.notes[0]


def test_passing_both_cases_is_agent() -> None:
    """2 of 2 is the agent level."""
    verdict = _plan(
        smoke=["passed"], pdf_brief=["passed"], board_pack=["passed"]
    ).verdict

    assert verdict is not None
    assert (verdict.level, verdict.passed, verdict.counted) == ("agent", 2, 2)


def test_failing_both_is_below_with_no_rerun() -> None:
    """Only a split earns a second run."""
    made = _plan(smoke=["passed"], pdf_brief=["failed"], board_pack=["failed"])

    assert made.next == []
    assert made.verdict is not None
    assert (made.verdict.level, made.verdict.passed) == ("below", 0)


def test_exactly_one_failed_case_is_run_once_more_and_a_pass_then_counts() -> None:
    """The re-run decides the case; passing it makes the model agent."""
    split = _plan(smoke=["passed"], pdf_brief=["passed"], board_pack=["failed"])
    assert split.next == [Next("board-pack")]
    assert split.verdict is None

    rescued = _plan(
        smoke=["passed"], pdf_brief=["passed"], board_pack=["failed", "passed"]
    ).verdict
    assert rescued is not None
    assert (rescued.level, rescued.passed, rescued.cells["board-pack"]) == (
        "agent",
        2,
        "pass",
    )
    assert "board-pack passed when run again" in rescued.notes


def test_a_second_failure_of_the_split_case_is_final() -> None:
    """There is no third run."""
    made = _plan(
        smoke=["passed"], pdf_brief=["failed", "failed"], board_pack=["passed"]
    )

    assert made.next == []
    assert made.verdict is not None
    assert (made.verdict.level, made.verdict.passed) == ("below", 1)
    assert made.verdict.notes[-1] == "pdf-brief, run again: pdf-brief failed"


def test_transient_and_harness_faults_get_two_retries_and_never_count() -> None:
    """The first try and two retries; then the case is unresolved, not failed."""
    retried = _plan(smoke=["transient", "harness", "passed"])
    assert [n.case for n in retried.next] == ["pdf-brief", "board-pack"]

    gave_up = _plan(smoke=["transient", "harness", "transient"]).verdict
    assert gave_up is not None
    assert gave_up.level is None
    assert gave_up.cells["smoke"] == "unresolved"
    assert gave_up.counted == 0
    assert "unresolved after 3 tries" in gave_up.notes[0]


def test_an_unresolved_case_leaves_the_model_unresolved_without_a_rerun() -> None:
    """No verdict is drawn from a case the model never got to answer."""
    made = _plan(
        smoke=["passed"],
        pdf_brief=["transient", "transient", "transient"],
        board_pack=["failed"],
    )

    assert made.next == []
    assert made.verdict is not None
    assert made.verdict.level is None
    assert (made.verdict.passed, made.verdict.counted) == (0, 1)


def test_interrupted_and_budget_attempts_use_up_no_retry() -> None:
    """Stopping the runner or running out of money is not the provider's fault either."""
    made = _plan(smoke=["interrupted", "transient", "budget", "transient", "passed"])

    assert [n.case for n in made.next] == ["pdf-brief", "board-pack"]


def test_reopening_gives_an_unresolved_case_its_retries_back() -> None:
    """--retry-unresolved reopens the case where it was left."""
    attempts = _cell("smoke", "transient", "transient", "transient")
    assert rolls(attempts)[-1].outcome == "unresolved"

    attempts.append(Attempt("m/x", "smoke", 0, "reopened"))
    (open_roll,) = rolls(attempts)
    assert open_roll.outcome is None
    assert plan({"smoke": attempts}, set()).next[0].case == "smoke"


def test_a_retry_waits_a_minute_after_the_fault() -> None:
    """A provider that just failed is not asked again at once."""
    (unit,) = plan({"smoke": _cell("smoke", "transient", ended=1000.0)}, set()).next

    assert unit.not_before == 1000.0 + RETRY_AFTER_SECONDS
