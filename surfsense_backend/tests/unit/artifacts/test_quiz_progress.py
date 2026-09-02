from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.artifacts.quiz import (
    QuizAnswerUpdate,
    QuizRetakeUpdate,
    QuizSkipUpdate,
    apply_quiz_answer,
    apply_quiz_retake,
    apply_quiz_skip,
    quiz_state_digest,
    sanitize_quiz_state,
)

USER_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_2 = UUID("00000000-0000-0000-0000-000000000002")


def test_answers_are_user_scoped_and_identical_retry_is_idempotent():
    metadata, first = apply_quiz_answer(
        {"verification": {"verified": True}},
        user_id=USER_1,
        generation=2,
        question_count=5,
        question_index=0,
        selected_option_index=1,
    )
    metadata, retried = apply_quiz_answer(
        metadata,
        user_id=USER_1,
        generation=2,
        question_count=5,
        question_index=0,
        selected_option_index=1,
    )
    other = sanitize_quiz_state(
        metadata,
        user_id=USER_2,
        generation=2,
        question_count=5,
    )

    assert first == retried
    assert retried["answers"] == {"0": 1}
    assert other["answers"] == {}
    assert other["skipped_question_indices"] == []
    assert metadata["verification"] == {"verified": True}


def test_different_answer_requires_retake():
    metadata, _ = apply_quiz_answer(
        None,
        user_id=USER_1,
        generation=1,
        question_count=5,
        question_index=0,
        selected_option_index=1,
    )
    with pytest.raises(RuntimeError, match="already answered"):
        apply_quiz_answer(
            metadata,
            user_id=USER_1,
            generation=1,
            question_count=5,
            question_index=0,
            selected_option_index=2,
        )


def test_skip_is_idempotent_user_scoped_and_conflicts_with_answer():
    metadata, first = apply_quiz_skip(
        None,
        user_id=USER_1,
        generation=1,
        question_count=5,
        question_index=2,
    )
    metadata, retried = apply_quiz_skip(
        metadata,
        user_id=USER_1,
        generation=1,
        question_count=5,
        question_index=2,
    )

    assert first == retried
    assert retried["skipped_question_indices"] == [2]
    assert (
        sanitize_quiz_state(
            metadata,
            user_id=USER_2,
            generation=1,
            question_count=5,
        )["skipped_question_indices"]
        == []
    )
    with pytest.raises(RuntimeError, match="already skipped"):
        apply_quiz_answer(
            metadata,
            user_id=USER_1,
            generation=1,
            question_count=5,
            question_index=2,
            selected_option_index=0,
        )


def test_retake_missed_includes_skipped_and_retake_all_clears():
    metadata = None
    answers = [0, 2, 2, 0, 1]
    correct = [0, 1, 2, 3, 1]
    for index, answer in enumerate(answers):
        if index == 3:
            metadata, _ = apply_quiz_skip(
                metadata,
                user_id=USER_1,
                generation=1,
                question_count=5,
                question_index=index,
            )
        else:
            metadata, _ = apply_quiz_answer(
                metadata,
                user_id=USER_1,
                generation=1,
                question_count=5,
                question_index=index,
                selected_option_index=answer,
            )

    metadata, missed = apply_quiz_retake(
        metadata,
        user_id=USER_1,
        generation=1,
        correct_option_indices=correct,
        mode="missed",
    )
    assert missed["active_question_indices"] == [1, 3]
    assert missed["answers"] == {"0": 0, "2": 2, "4": 1}
    assert missed["skipped_question_indices"] == []

    metadata, _ = apply_quiz_answer(
        metadata,
        user_id=USER_1,
        generation=1,
        question_count=5,
        question_index=1,
        selected_option_index=1,
    )
    metadata, _ = apply_quiz_answer(
        metadata,
        user_id=USER_1,
        generation=1,
        question_count=5,
        question_index=3,
        selected_option_index=3,
    )
    _, all_state = apply_quiz_retake(
        metadata,
        user_id=USER_1,
        generation=1,
        correct_option_indices=correct,
        mode="all",
    )
    assert all_state["answers"] == {}
    assert all_state["active_question_indices"] == [0, 1, 2, 3, 4]
    assert all_state["skipped_question_indices"] == []


def test_requests_are_closed_strict_and_digest_is_canonical():
    assert (
        QuizAnswerUpdate(
            generation=1, question_index=0, selected_option_index=3
        ).selected_option_index
        == 3
    )
    assert QuizSkipUpdate(generation=1, question_index=2).question_index == 2
    assert QuizRetakeUpdate(generation=1, mode="missed").mode == "missed"
    with pytest.raises(ValidationError):
        QuizAnswerUpdate(
            generation=True,
            question_index=0,
            selected_option_index=1,
        )
    first = {
        "generation": 1,
        "mode": "all",
        "active_question_indices": [0],
        "answers": {"0": 1},
        "skipped_question_indices": [],
    }
    assert quiz_state_digest(first) == quiz_state_digest(dict(reversed(first.items())))


def test_state_without_explicit_skipped_indexes_is_rejected():
    metadata = {
        "quiz": {
            "progress_by_user": {
                str(USER_1): {
                    "generation": 1,
                    "mode": "all",
                    "active_question_indices": [0],
                    "answers": {"0": 1},
                }
            }
        }
    }
    assert (
        sanitize_quiz_state(
            metadata,
            user_id=USER_1,
            generation=1,
            question_count=1,
        )["answers"]
        == {}
    )
