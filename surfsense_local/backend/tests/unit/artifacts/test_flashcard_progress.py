import pytest
from fastapi import HTTPException

from modules.artifacts.flashcard_progress import (
    apply_flashcard_mark,
    apply_flashcard_order,
    empty_flashcard_state,
    reset_flashcard_progress,
    sanitize_flashcard_state,
)

pytestmark = pytest.mark.unit


def test_marking_is_idempotent_and_does_not_disturb_other_metadata_keys():
    """A retried identical mark must not error, and must leave the
    artifact's other metadata (prompt, options, ...) untouched."""
    metadata, first = apply_flashcard_mark(
        {"prompt": "focus on rings"},
        generation=1,
        card_count=5,
        card_index=0,
        mark="good",
    )
    metadata, retried = apply_flashcard_mark(
        metadata, generation=1, card_count=5, card_index=0, mark="good"
    )

    assert first == retried
    assert retried["marks"] == {"0": "good"}
    assert metadata["prompt"] == "focus on rings"


def test_a_mark_can_be_changed_freely_unlike_a_quiz_answer():
    """Flashcard marks are a study aid, not a scored run, so — unlike a
    quiz answer — changing one needs no retake."""
    metadata, _ = apply_flashcard_mark(
        None, generation=1, card_count=5, card_index=0, mark="again"
    )
    _, state = apply_flashcard_mark(
        metadata, generation=1, card_count=5, card_index=0, mark="good"
    )

    assert state["marks"] == {"0": "good"}


def test_clearing_a_mark_with_null_removes_it():
    """Passing mark=None un-marks a card instead of storing a null mark."""
    metadata, _ = apply_flashcard_mark(
        None, generation=1, card_count=5, card_index=0, mark="good"
    )
    _, state = apply_flashcard_mark(
        metadata, generation=1, card_count=5, card_index=0, mark=None
    )

    assert state["marks"] == {}


def test_a_card_index_outside_the_deck_is_rejected():
    """An index outside the deck's card count can't be marked."""
    with pytest.raises(HTTPException):
        apply_flashcard_mark(
            None, generation=1, card_count=5, card_index=9, mark="good"
        )


def test_a_stale_generation_is_treated_as_an_empty_deck():
    """Regenerating a deck bumps its generation; old progress under a prior
    generation must be discarded rather than misapplied to the new deck."""
    metadata, _ = apply_flashcard_mark(
        None, generation=1, card_count=5, card_index=0, mark="good"
    )
    state = sanitize_flashcard_state(metadata, generation=2, card_count=5)

    assert state == empty_flashcard_state(generation=2, card_count=5)


def test_reset_clears_marks_but_keeps_the_shuffle_order():
    """A reset starts a fresh study pass over the same shuffled order,
    rather than also reverting to the canonical card ordering."""
    metadata, _ = apply_flashcard_mark(
        None, generation=1, card_count=3, card_index=0, mark="good"
    )
    metadata, _ = apply_flashcard_order(
        metadata, generation=1, card_count=3, order=[2, 0, 1]
    )

    _, state = reset_flashcard_progress(metadata, generation=1, card_count=3)

    assert state["marks"] == {}
    assert state["order"] == [2, 0, 1]


def test_reordering_requires_every_index_exactly_once():
    """A shuffle order must be a permutation of every card index — not
    short, not long, and never repeating one."""
    with pytest.raises(HTTPException):
        apply_flashcard_order(None, generation=1, card_count=3, order=[0, 1])
    with pytest.raises(HTTPException):
        apply_flashcard_order(None, generation=1, card_count=3, order=[0, 1, 1])
