"""A run's counts as the Jobs screen and the agent give them: each question answered, left to a
person, or carrying a suggested answer one step confirms, once each."""

import pytest

from modules.agent.tool_endpoint.run_job import summary
from modules.jobs.runs.run_tally import run_tally

pytestmark = pytest.mark.unit

CONFIRM = {"answer": "N/A", "written": "N/A", "comment": "Hosted by Google Cloud."}


def answer(codes: list[str], confirm: dict | None = None) -> dict:
    """One answer of a report, as the run's pipeline writes it."""
    return {"sheet": "Questions", "cell": "B2", "codes": codes, "confirm": confirm}


REPORT = {
    "questions": 5,
    "counts": {"Yes": 2, "Needs review": 3, "blank": 3, "skipped": 4},
    "answers": [
        answer([]),
        answer([]),
        answer(["SUGGESTED", "NEEDS_REVIEW"], CONFIRM),
        # A suggestion its cell's dropdown cannot hold: on the exceptions sheet for a person.
        answer(["SUGGESTED", "NEEDS_REVIEW"]),
        answer(["QUOTE_NOT_FOUND", "NEEDS_REVIEW"]),
    ],
}


def test_every_question_is_answered_left_to_a_person_or_suggested() -> None:
    """The three add up to the questions, so the screen's lines account for every row."""
    tally = run_tally(REPORT)

    assert tally == {
        "questions": 5,
        "answered": 2,
        "for_person": 2,
        "suggested": 1,
        "skipped": 4,
    }
    assert tally["answered"] + tally["for_person"] + tally["suggested"] == 5


def test_a_suggestion_is_counted_once() -> None:
    """A suggestion is also left for review; it is counted as the suggestion it is."""
    tally = run_tally({**REPORT, "questions": 1, "answers": [REPORT["answers"][2]]})

    assert (tally["answered"], tally["for_person"], tally["suggested"]) == (0, 0, 1)


def test_skipped_rows_come_from_the_counts() -> None:
    """Rows hidden, locked or already answered were never questions of the run."""
    tally = run_tally({**REPORT, "counts": {"Yes": 2}})

    assert tally["skipped"] == 0
    assert tally["questions"] == 5


def test_a_run_without_a_report_has_no_tally() -> None:
    """Until the worker has written its report, there is nothing to count."""
    assert run_tally(None) is None


@pytest.mark.parametrize(
    ("suggestions", "said"),
    [
        (2, "2 questions carry a suggested answer"),
        (1, "1 question carries a suggested"),
    ],
)
def test_the_agent_s_reply_counts_suggestions_as_its_tally_does(
    suggestions: int, said: str
) -> None:
    """The reply's line on suggestions agrees with its tally, which counts a suggestion apart
    from the questions left to a person, as the Jobs screen does."""
    report = {
        "questions": suggestions,
        "counts": {"Needs review": suggestions},
        "suggested": suggestions,
        "sheets": {
            "answers": "SurfSense answers",
            "exceptions": "SurfSense exceptions",
        },
        "answers": [answer(["SUGGESTED", "NEEDS_REVIEW"], CONFIRM)] * suggestions,
        "exceptions": [],
    }

    reply = summary(41, report)

    assert (
        f"{suggestions} questions: 0 answered, 0 left to a person, {suggestions} with a "
        "suggested answer to confirm" in reply
    )
    assert said in reply
    assert "left to a person carry" not in reply
