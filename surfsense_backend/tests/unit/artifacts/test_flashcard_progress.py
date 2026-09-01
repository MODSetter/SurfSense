from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.artifacts.flashcards import (
    FlashcardOrderUpdate,
    FlashcardProgressUpdate,
    apply_flashcard_mark,
    apply_flashcard_order,
    reset_flashcard_progress,
    sanitize_flashcard_study_state,
    study_state_digest,
)

USER_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_2 = UUID("00000000-0000-0000-0000-000000000002")
USER_3 = UUID("00000000-0000-0000-0000-000000000003")


def _state(
    *,
    generation: int = 3,
    marks: dict[str, str] | None = None,
    order: list[int] | None = None,
) -> dict[str, object]:
    return {
        "generation": generation,
        "marks": marks or {},
        "order": order or [0, 1, 2],
    }


def test_sanitizes_only_the_current_users_valid_state():
    metadata = {
        "flashcards": {
            "study_by_user": {
                str(USER_1): _state(marks={"0": "good", "2": "invalid"}),
                str(USER_2): _state(marks={"1": "again"}, order=[2, 0, 1]),
                "bad": _state(),
            }
        }
    }

    assert sanitize_flashcard_study_state(
        metadata, user_id=USER_1, generation=3, card_count=3
    ) == {
        "generation": 3,
        "marks": {"0": "good"},
        "order": [0, 1, 2],
    }
    assert sanitize_flashcard_study_state(
        metadata, user_id=USER_2, generation=3, card_count=3
    ) == {
        "generation": 3,
        "marks": {"1": "again"},
        "order": [2, 0, 1],
    }
    assert sanitize_flashcard_study_state(
        metadata, user_id=USER_3, generation=3, card_count=3
    ) == {
        "generation": 3,
        "marks": {},
        "order": [0, 1, 2],
    }


def test_mark_updates_only_the_authenticated_user():
    metadata = {
        "verification": {"verified": True},
        "flashcards": {
            "study_by_user": {
                str(USER_1): _state(marks={"0": "good"}),
                str(USER_2): _state(marks={"1": "again"}, order=[2, 0, 1]),
            }
        },
    }

    updated, state = apply_flashcard_mark(
        metadata,
        user_id=USER_1,
        generation=3,
        card_count=3,
        card_index=2,
        mark="again",
    )

    assert state["marks"] == {"0": "good", "2": "again"}
    assert updated["verification"] == {"verified": True}
    assert updated["flashcards"]["study_by_user"][str(USER_2)] == _state(
        marks={"1": "again"}, order=[2, 0, 1]
    )


def test_shuffle_and_reset_are_user_scoped_and_preserve_each_other():
    metadata, shuffled = apply_flashcard_order(
        None,
        user_id=USER_1,
        generation=3,
        card_count=3,
        order=[2, 0, 1],
    )
    metadata, _ = apply_flashcard_mark(
        metadata,
        user_id=USER_1,
        generation=3,
        card_count=3,
        card_index=2,
        mark="good",
    )
    metadata, reset = reset_flashcard_progress(
        metadata,
        user_id=USER_1,
        generation=3,
        card_count=3,
    )

    assert shuffled["order"] == [2, 0, 1]
    assert reset == {"generation": 3, "marks": {}, "order": [2, 0, 1]}
    assert metadata["flashcards"]["study_by_user"][str(USER_1)] == reset


def test_reset_removes_empty_canonical_user_entry():
    metadata, _ = apply_flashcard_mark(
        None,
        user_id=USER_1,
        generation=3,
        card_count=3,
        card_index=0,
        mark="good",
    )

    updated, state = reset_flashcard_progress(
        metadata,
        user_id=USER_1,
        generation=3,
        card_count=3,
    )

    assert updated == {}
    assert state == {"generation": 3, "marks": {}, "order": [0, 1, 2]}


def test_rejects_invalid_indexes_and_orders():
    with pytest.raises(ValueError, match="outside"):
        apply_flashcard_mark(
            None,
            user_id=USER_1,
            generation=3,
            card_count=3,
            card_index=3,
            mark="good",
        )
    with pytest.raises(ValueError, match="exactly once"):
        apply_flashcard_order(
            None,
            user_id=USER_1,
            generation=3,
            card_count=3,
            order=[0, 0, 2],
        )


def test_study_state_digest_is_canonical_and_covers_order():
    first = {"generation": 3, "marks": {"0": "good"}, "order": [0, 1, 2]}
    reordered = {"order": [0, 1, 2], "marks": {"0": "good"}, "generation": 3}
    shuffled = {"generation": 3, "marks": {"0": "good"}, "order": [2, 0, 1]}

    assert study_state_digest(first) == study_state_digest(reordered)
    assert study_state_digest(first) != study_state_digest(shuffled)


def test_update_requests_are_closed_and_strict():
    assert (
        FlashcardProgressUpdate(generation=1, card_index=0, mark="good").mark == "good"
    )
    assert FlashcardOrderUpdate(generation=1, order=[1, 0]).order == [1, 0]
    with pytest.raises(ValidationError):
        FlashcardProgressUpdate(generation=True, card_index=0, mark="good")
    with pytest.raises(ValidationError):
        FlashcardOrderUpdate(generation=1, order=[0, 0], extra=True)
