"""What a model runs next, and its verdict once nothing is left: smoke first, then the PDF brief and the board pack.

A smoke the model fails stops it at 0 of 2. A transient or harness failure is
tried up to twice more and never counted; three in a row leave the case
unresolved, and so the model. When exactly one of the two cases fails for the
model's own reasons it is run once more, and that run decides the case.
"""

from dataclasses import dataclass, field
from typing import Literal

from tests.live.sweep.attempt import Attempt

SMOKE = "smoke"
SCORED = ("pdf-brief", "board-pack")
CASES = (SMOKE, *SCORED)
RETRIES = 2
# A provider that just failed gets a minute before the same case goes back to it.
RETRY_AFTER_SECONDS = 60.0

RollOutcome = Literal["passed", "failed", "unresolved"]
Cell = Literal["pass", "fail", "not_run", "unresolved"]


@dataclass(frozen=True)
class Roll:
    """One counted try at a case, with the uncounted tries that led to it."""

    outcome: RollOutcome | None
    attempts: list[Attempt]

    @property
    def deciding(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None


@dataclass(frozen=True)
class Next:
    case: str
    # Epoch seconds before which it must not start.
    not_before: float = 0.0


@dataclass(frozen=True)
class Verdict:
    # None while a case is unresolved.
    level: Literal["agent", "below"] | None
    passed: int
    counted: int
    run: int
    cells: dict[str, Cell]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModelPlan:
    next: list[Next]
    verdict: Verdict | None


def rolls(attempts: list[Attempt]) -> list[Roll]:
    """One case's attempts as rolls, the last possibly still open."""
    found: list[Roll] = []
    current: list[Attempt] = []
    tries = 0
    for attempt in attempts:
        if attempt.outcome == "reopened":
            if not current and found and found[-1].outcome == "unresolved":
                current, tries = found.pop().attempts, 0
            continue
        current.append(attempt)
        if attempt.counted:
            found.append(Roll(attempt.outcome, current))  # type: ignore[arg-type]
            current, tries = [], 0
        elif attempt.uses_a_try:
            tries += 1
            if tries > RETRIES:
                found.append(Roll("unresolved", current))
                current, tries = [], 0
    if current:
        found.append(Roll(None, current))
    return found


def plan(by_case: dict[str, list[Attempt]], in_flight: set[str]) -> ModelPlan:
    """The cases to start (not those in flight), or the verdict once none is left."""
    smoke = _decided(by_case, SMOKE, 0)
    if smoke is None:
        return ModelPlan(_start(by_case, SMOKE, in_flight), None)
    if smoke.outcome == "failed":
        reason = smoke.deciding.reason if smoke.deciding else ""
        return ModelPlan(
            [],
            Verdict(
                "below",
                0,
                len(SCORED),
                0,
                {SMOKE: "fail", **dict.fromkeys(SCORED, "not_run")},
                [f"smoke failed, so the two cases were not run: {reason}".strip()],
            ),
        )
    if smoke.outcome == "unresolved":
        return ModelPlan([], _unresolved({SMOKE: "unresolved"}, [_why(SMOKE, smoke)]))

    firsts = {case: _decided(by_case, case, 0) for case in SCORED}
    waiting = [case for case, roll in firsts.items() if roll is None]
    if waiting:
        return ModelPlan(
            [n for case in waiting for n in _start(by_case, case, in_flight)], None
        )
    cells: dict[str, Cell] = {SMOKE: "pass"}
    notes: list[str] = []
    unresolved = False
    for case, roll in firsts.items():
        assert roll is not None
        cells[case] = _cell(roll)
        if roll.outcome == "unresolved":
            unresolved = True
            notes.append(_why(case, roll))
        elif roll.outcome == "failed":
            notes.append(_why(case, roll))
    failed = [case for case, cell in cells.items() if cell == "fail"]
    if not unresolved and len(failed) == 1:
        (case,) = failed
        second = _decided(by_case, case, 1)
        if second is None:
            return ModelPlan(_start(by_case, case, in_flight, roll=1), None)
        cells[case] = _cell(second)
        if second.outcome == "passed":
            notes.append(f"{case} passed when run again")
        else:
            notes.append(f"{case} run again: {_why(case, second)}")
            unresolved = unresolved or second.outcome == "unresolved"
    if unresolved:
        return ModelPlan([], _unresolved(cells, notes))
    passed = sum(cells[case] == "pass" for case in SCORED)
    return ModelPlan(
        [],
        Verdict(
            "agent" if passed == len(SCORED) else "below",
            passed,
            len(SCORED),
            len(SCORED),
            cells,
            notes,
        ),
    )


def _decided(by_case: dict[str, list[Attempt]], case: str, index: int) -> Roll | None:
    """The case's roll at `index` once it is decided, else None."""
    found = rolls(by_case.get(case, []))
    if len(found) <= index or found[index].outcome is None:
        return None
    return found[index]


def _start(
    by_case: dict[str, list[Attempt]], case: str, in_flight: set[str], roll: int = 0
) -> list[Next]:
    """The case's next attempt, once the last uncounted one has had its pause."""
    if case in in_flight:
        return []
    found = rolls(by_case.get(case, []))
    open_roll = found[roll] if len(found) > roll else None
    tried = [a for a in (open_roll.attempts if open_roll else []) if a.uses_a_try]
    not_before = tried[-1].ended + RETRY_AFTER_SECONDS if tried else 0.0
    return [Next(case, not_before)]


def _cell(roll: Roll) -> Cell:
    return {"passed": "pass", "failed": "fail"}.get(roll.outcome or "", "unresolved")  # type: ignore[return-value]


def _why(case: str, roll: Roll) -> str:
    last = roll.deciding
    if roll.outcome == "unresolved":
        return f"{case} unresolved after {len(roll.attempts)} tries: {last.reason if last else ''}"
    return f"{case}: {last.reason if last else ''}"


def _unresolved(cells: dict[str, Cell], notes: list[str]) -> Verdict:
    full = {case: cells.get(case, "not_run") for case in CASES}
    passed = sum(full[case] == "pass" for case in SCORED)
    counted = sum(full[case] in ("pass", "fail") for case in SCORED)
    return Verdict(None, passed, counted, counted, full, notes)
