"""A run's counts as the Jobs screen and the agent give them: each question or review point
settled, left to a person, or carrying a suggested answer one step confirms, and the rows left as
they were."""

from __future__ import annotations

from typing import Any


def run_tally(report: dict[str, Any] | None) -> dict[str, int] | None:
    """None before the run has a report. Every question, or a contract's review point, is
    counted once, so `answered`, `for_person` and `suggested` add up to `questions`; a suggestion
    its cell cannot hold is left to a person, as the exceptions sheet says."""
    if report is None:
        return None
    answers = report.get("answers") or []
    suggested = sum(1 for answer in answers if answer.get("confirm"))
    answered = sum(
        1 for answer in answers if not answer.get("confirm") and not answer.get("codes")
    )
    return {
        "questions": report.get("questions", report.get("points", len(answers))),
        "answered": answered,
        "for_person": len(answers) - answered - suggested,
        "suggested": suggested,
        "skipped": (report.get("counts") or {}).get("skipped", 0),
    }
