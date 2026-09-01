from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.artifacts.flashcards import (
    FlashcardProgressUpdate,
    apply_flashcard_mark,
    progress_digest,
    reset_flashcard_progress,
    sanitize_flashcard_progress,
)


def test_sanitizes_only_current_bounded_marks():
    metadata = {
        "flashcards": {
            "progress": {
                "generation": 3,
                "marks": {
                    "0": "good",
                    "1": "again",
                    "2": "invalid",
                    "99": "good",
                    "-1": "again",
                },
            }
        }
    }

    assert sanitize_flashcard_progress(metadata, generation=3, card_count=3) == {
        "generation": 3,
        "marks": {"0": "good", "1": "again"},
    }
    assert sanitize_flashcard_progress(metadata, generation=4, card_count=3) == {
        "generation": 4,
        "marks": {},
    }


def test_apply_mark_preserves_unrelated_metadata_and_supports_unseen():
    metadata = {
        "verification": {"verified": True},
        "flashcards": {"future": "preserve"},
    }
    updated, progress = apply_flashcard_mark(
        metadata,
        generation=2,
        card_count=2,
        card_index=1,
        mark="again",
    )

    assert updated["verification"] == {"verified": True}
    assert updated["flashcards"]["future"] == "preserve"
    assert progress == {"generation": 2, "marks": {"1": "again"}}

    updated, progress = apply_flashcard_mark(
        updated,
        generation=2,
        card_count=2,
        card_index=1,
        mark=None,
    )
    assert progress == {"generation": 2, "marks": {}}


def test_serialized_updates_merge_different_cards_and_reject_bad_indexes():
    metadata, _ = apply_flashcard_mark(
        None,
        generation=1,
        card_count=2,
        card_index=0,
        mark="good",
    )
    metadata, progress = apply_flashcard_mark(
        metadata,
        generation=1,
        card_count=2,
        card_index=1,
        mark="again",
    )

    assert progress == {
        "generation": 1,
        "marks": {"0": "good", "1": "again"},
    }
    with pytest.raises(ValueError, match="outside"):
        apply_flashcard_mark(
            metadata,
            generation=1,
            card_count=2,
            card_index=2,
            mark="good",
        )


def test_progress_digest_is_order_independent_and_changes_with_marks():
    first = {"generation": 1, "marks": {"0": "good", "1": "again"}}
    reordered = {"marks": {"1": "again", "0": "good"}, "generation": 1}
    changed = {"generation": 1, "marks": {"0": "again", "1": "again"}}

    assert progress_digest(first) == progress_digest(reordered)
    assert progress_digest(first) != progress_digest(changed)


def test_reset_progress_removes_only_progress_namespace():
    metadata = {
        "verification": {"verified": True},
        "flashcards": {
            "future": "preserve",
            "progress": {"generation": 3, "marks": {"0": "good"}},
        },
    }

    updated, progress = reset_flashcard_progress(metadata, generation=3)

    assert updated == {
        "verification": {"verified": True},
        "flashcards": {"future": "preserve"},
    }
    assert progress == {"generation": 3, "marks": {}}


def test_progress_request_is_closed_and_strict():
    assert (
        FlashcardProgressUpdate(generation=1, card_index=0, mark="good").mark == "good"
    )
    with pytest.raises(ValidationError):
        FlashcardProgressUpdate(
            generation=True,
            card_index=0,
            mark="good",
        )
    with pytest.raises(ValidationError):
        FlashcardProgressUpdate(
            generation=1,
            card_index=0,
            mark="good",
            extra=True,
        )
