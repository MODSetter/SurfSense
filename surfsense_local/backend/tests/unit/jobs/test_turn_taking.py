"""Two models that cannot be loaded at once take turns: a run calls one for many questions, then
the other, instead of switching twice a question."""

import json
import threading
import time
from itertools import pairwise
from pathlib import Path

import openpyxl
import pytest

from modules.jobs.evidence.passages import SourceText
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import FillStoppedError, fill_workbook

pytestmark = pytest.mark.unit

QUOTE = "Access to client data is granted on a least-privilege basis."
POLICY = SourceText(1, "access", f"## Access\n\n{QUOTE}")
QUESTIONS = 6


@pytest.fixture
def config(tmp_path: Path):
    """A job whose Yes answers are checked."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    for name, text in {
        "system": "system: $answers",
        "question": "$passages\n\nQuestion: $question",
        "repair": "$problem",
        "verify": "verify: $answer",
    }.items():
        (folder / "prompts" / f"{name}.md").write_text(text, encoding="utf-8")
    (folder / "job.json").write_text(
        json.dumps(
            {
                "answers": [
                    {"answer": "Yes", "needs_quote": True},
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {"question": ["question"], "answer": ["answer"]},
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "verify": {"prompt": "prompts/verify.md", "answers": ["Yes"]},
                "templates": {"comment": {"*": "$comment"}, "evidence": "$where"},
                "sheets": {"answers": "Answers", "exceptions": "Exceptions"},
            }
        ),
        encoding="utf-8",
    )
    return load_config(folder / "job.json")


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """Six questions, free-text answers."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer"])
    for number in range(QUESTIONS):
        sheet.append([f"Is access to system {number} least privilege?", None])
    path = tmp_path / "Q.xlsx"
    book.save(path)
    return path


class Logged:
    """One of the two models: answers Yes with the policy's sentence, or checks; every call it
    gets goes in the shared log, and two at once would mean both were loaded."""

    window = 32_768
    concurrency = 1

    def __init__(self, name: str, log: list[str], held: list[int], refuse: set[str]):
        self.name = name
        self._log = log
        self._held = held
        self._refuse = refuse

    def ask(self, system, turns, schema, shared):
        self._held[0] += 1
        try:
            assert self._held[0] == 1, "two calls at once on a one-slot runtime"
            self._log.append(self.name)
            time.sleep(0.002)
            if system.startswith("verify"):
                question = turns[0][1]
                refused = any(word in question for word in self._refuse)
                # A refused row is refused once: its second check passes.
                self._refuse.difference_update(
                    {w for w in self._refuse if w in question}
                )
                return ModelReply(
                    json.dumps({"supported": not refused, "missing": "Off topic."})
                )
            return ModelReply(
                json.dumps(
                    {
                        "quotes": [{"passage": 1, "quote": QUOTE}],
                        "answer": "Yes",
                        "comment": "Least privilege.",
                        "confidence": "high",
                    }
                )
            )
        finally:
            self._held[0] -= 1


def _switches(log: list[str]) -> int:
    return sum(1 for before, after in pairwise(log) if before != after)


def _pair(refuse: set[str] | None = None):
    log: list[str] = []
    held = [0]
    refusing = refuse or set()
    return (
        log,
        Logged("answer", log, held, refusing),
        Logged("check", log, held, refusing),
    )


def test_every_question_is_answered_before_the_checks_begin(workbook, config):
    """One turn for the answers, one for the checks: the runtime loads each model once."""
    log, answering, checking = _pair()

    filled = fill_workbook(
        workbook, [POLICY], config, answering, checker=checking, take_turns=True
    )

    assert [r.answer for r in filled.results] == ["Yes"] * QUESTIONS
    assert log == ["answer"] * QUESTIONS + ["check"] * QUESTIONS


def test_a_question_asked_again_after_a_refusal_waits_for_the_next_turn(
    workbook, config
):
    """The refused question is asked again in a second answering turn, then checked again."""
    log, answering, checking = _pair(refuse={"system 2 "})

    filled = fill_workbook(
        workbook, [POLICY], config, answering, checker=checking, take_turns=True
    )

    assert [r.answer for r in filled.results] == ["Yes"] * QUESTIONS
    assert _switches(log) == 3
    assert log.count("answer") == QUESTIONS + 1 and log.count("check") == QUESTIONS + 1


def test_without_turns_each_question_switches_models(workbook, config):
    """The cost the turns avoid: answered one at a time, a question checks right after it is
    answered."""
    log, answering, checking = _pair()

    fill_workbook(workbook, [POLICY], config, answering, checker=checking)

    assert _switches(log) == 2 * QUESTIONS - 1


def test_a_question_whose_call_fails_does_not_hold_up_the_turns(workbook, config):
    """A failed call frees its turn: the question goes to a person and the others go on."""
    log, answering, checking = _pair()
    asked = answering.ask

    def failing(system, turns, schema, shared):
        if "system 3 " in turns[-1][1]:
            raise RuntimeError("connection reset")
        return asked(system, turns, schema, shared)

    answering.ask = failing

    filled = fill_workbook(
        workbook, [POLICY], config, answering, checker=checking, take_turns=True
    )

    assert sum("CALL_FAILED" in r.codes for r in filled.results) == 1
    assert _switches(log) == 1


def test_a_cancel_stops_questions_waiting_for_their_turn(workbook, config, monkeypatch):
    """A cancel is read on the run's own thread while the questions are under way, and stops
    every call not yet made: no check is asked."""
    monkeypatch.setattr("modules.jobs.asking.answer_all.STOP_POLL_SECONDS", 0.01)
    log, answering, checking = _pair()
    asked = answering.ask
    cancel = threading.Event()

    def slow(system, turns, schema, shared):
        reply = asked(system, turns, schema, shared)
        cancel.set()
        time.sleep(0.05)
        return reply

    answering.ask = slow
    outcome: list[BaseException] = []

    def run():
        try:
            fill_workbook(
                workbook,
                [POLICY],
                config,
                answering,
                checker=checking,
                take_turns=True,
                stop=cancel.is_set,
            )
        except BaseException as stopped:
            outcome.append(stopped)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=30)

    assert not thread.is_alive(), "the run hung"
    assert outcome and isinstance(outcome[0], FillStoppedError)
    assert "check" not in log
