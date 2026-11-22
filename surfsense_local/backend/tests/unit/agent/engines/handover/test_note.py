"""The note an engine taking over a thread is given: what happened while it was away."""

from typing import Any

import pytest

from modules.agent.engines.handover.note import TAG, handover_note

pytestmark = pytest.mark.unit


def _turn(text: str, reply: str, steps: list[dict[str, Any]] = ()) -> list[dict]:
    return [
        {"role": "user", "content": {"text": text}},
        {"role": "assistant", "content": {"text": reply, "steps": list(steps)}},
    ]


def _step(tool: str, given: dict, output: str = "", error: str | None = None) -> dict:
    return {"tool": tool, "input": given, "output": output, "error": error}


def test_the_note_holds_each_message_reply_call_and_the_files_made() -> None:
    """In the order they happened, tagged so reading the thread back takes it out."""
    turns = _turn(
        "What grew in Q3?",
        "Revenue grew 12%.",
        [_step("surfsense_search_sources", {"query": "Q3"}, "[1] Revenue up 12%.")],
    )

    note = handover_note(turns, ["outputs/q3.md"], budget=10_000)

    assert note.startswith(f"<{TAG}>")
    assert note.rstrip().endswith(f"</{TAG}>")
    assert "What grew in Q3?" in note
    assert "Revenue grew 12%." in note
    assert 'surfsense_search_sources {"query": "Q3"}' in note
    assert "[1] Revenue up 12%." in note
    assert "outputs/q3.md" in note


def test_a_long_tool_output_is_cut() -> None:
    """2,000 characters of each, as the proposal sets."""
    turns = _turn("Read it", "Done.", [_step("read", {"filePath": "a.md"}, "x" * 5000)])

    note = handover_note(turns, [], budget=100_000)

    assert "x" * 2000 in note
    assert "x" * 2001 not in note


def test_what_a_file_said_before_it_was_rewritten_is_left_out() -> None:
    """The file is on disk as it is now; its old text would only mislead."""
    turns = _turn(
        "Fix the draft",
        "Fixed.",
        [
            _step("read", {"filePath": "outputs/draft.md"}, "OLD DRAFT TEXT"),
            _step("write", {"filePath": "outputs/draft.md", "content": "new"}),
        ],
    )

    note = handover_note(turns, ["outputs/draft.md"], budget=100_000)

    assert "OLD DRAFT TEXT" not in note
    assert "outputs/draft.md" in note


def test_too_long_a_note_loses_older_tool_outputs_first() -> None:
    """The newest turns stay whole; the oldest calls keep their names, not their outputs."""
    old = _turn(
        "First", "First answer.", [_step("read", {"filePath": "a"}, "A" * 1500)]
    )
    new = _turn(
        "Second", "Second answer.", [_step("read", {"filePath": "b"}, "B" * 1500)]
    )

    note = handover_note([*old, *new], [], budget=2500)

    assert "B" * 1500 in note
    assert "A" * 1500 not in note
    assert "First answer." in note
    assert len(note) <= 2500


def test_a_note_that_still_does_not_fit_keeps_the_newest_turns() -> None:
    """The oldest turns go last of all, and the newest is never cut away."""
    turns = []
    for n in range(50):
        turns += _turn(f"Question {n}", f"Answer {n}. " + "word " * 100)

    note = handover_note(turns, [], budget=3000)

    assert len(note) <= 3000
    assert "Question 49" in note
    assert "Answer 49." in note
