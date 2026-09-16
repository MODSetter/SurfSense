import pytest
from fastapi import HTTPException

from modules.artifacts.quiz_progress import (
    apply_quiz_answer,
    apply_quiz_retake,
    apply_quiz_skip,
    empty_quiz_state,
    quiz_run_complete,
    sanitize_quiz_state,
)

pytestmark = pytest.mark.unit


def test_answering_is_idempotent_and_does_not_disturb_other_metadata_keys():
    """A retried identical answer must not error, and must leave the
    artifact's other metadata (prompt, options, ...) untouched."""
    metadata, first = apply_quiz_answer(
        {"prompt": "focus on rings"},
        generation=2,
        question_count=5,
        question_index=0,
        selected_option_index=1,
    )
    metadata, retried = apply_quiz_answer(
        metadata,
        generation=2,
        question_count=5,
        question_index=0,
        selected_option_index=1,
    )

    assert first == retried
    assert retried["answers"] == {"0": 1}
    assert metadata["prompt"] == "focus on rings"


def test_changing_an_answer_without_a_retake_is_rejected():
    """An answered question is locked in; changing it requires a retake."""
    metadata, _ = apply_quiz_answer(
        None, generation=1, question_count=5, question_index=0, selected_option_index=1
    )
    with pytest.raises(HTTPException):
        apply_quiz_answer(
            metadata,
            generation=1,
            question_count=5,
            question_index=0,
            selected_option_index=2,
        )


def test_answering_a_skipped_question_is_rejected():
    """A skipped question can't also be answered without a retake."""
    metadata, _ = apply_quiz_skip(None, generation=1, question_count=5, question_index=0)
    with pytest.raises(HTTPException):
        apply_quiz_answer(
            metadata,
            generation=1,
            question_count=5,
            question_index=0,
            selected_option_index=1,
        )


def test_a_stale_generation_is_treated_as_an_empty_run():
    """Regenerating a quiz bumps its generation; old progress under a prior
    generation must be discarded rather than misapplied to the new quiz."""
    metadata, _ = apply_quiz_answer(
        None, generation=1, question_count=5, question_index=0, selected_option_index=1
    )
    state = sanitize_quiz_state(metadata, generation=2, question_count=5)

    assert state == empty_quiz_state(generation=2, question_count=5)


def test_retake_missed_only_rescopes_the_wrong_answers():
    """A "missed" retake narrows the run to the wrong answers only, clearing
    just those while leaving already-correct ones recorded."""
    metadata, _ = apply_quiz_answer(
        None, generation=1, question_count=3, question_index=0, selected_option_index=0
    )
    metadata, _ = apply_quiz_answer(
        metadata, generation=1, question_count=3, question_index=1, selected_option_index=3
    )
    metadata, _ = apply_quiz_answer(
        metadata, generation=1, question_count=3, question_index=2, selected_option_index=0
    )

    metadata, state = apply_quiz_retake(
        metadata,
        generation=1,
        correct_option_indices=[0, 0, 0],
        mode="missed",
    )

    assert state["mode"] == "missed"
    assert state["active_question_indices"] == [1]
    # The missed question's prior answer is cleared for a fresh attempt; the
    # already-correct ones outside the retake's scope are left untouched.
    assert state["answers"] == {"0": 0, "2": 0}


def test_retake_all_clears_everything():
    """An "all" retake wipes every answer and skip, back to a fresh run."""
    metadata, _ = apply_quiz_answer(
        None, generation=1, question_count=2, question_index=0, selected_option_index=0
    )
    metadata, _ = apply_quiz_skip(metadata, generation=1, question_count=2, question_index=1)

    metadata, state = apply_quiz_retake(
        metadata, generation=1, correct_option_indices=[0, 0], mode="all"
    )

    assert state == empty_quiz_state(generation=1, question_count=2)


def test_retake_before_the_run_is_complete_is_rejected():
    """Retaking mid-run would silently drop in-progress answers, so it's
    refused until every active question is answered or skipped."""
    metadata, _ = apply_quiz_answer(
        None, generation=1, question_count=3, question_index=0, selected_option_index=0
    )
    with pytest.raises(HTTPException):
        apply_quiz_retake(
            metadata, generation=1, correct_option_indices=[0, 0, 0], mode="all"
        )


def test_a_question_index_outside_the_active_scope_is_rejected():
    """An index outside the quiz's question count can't be answered."""
    with pytest.raises(HTTPException):
        apply_quiz_answer(
            None, generation=1, question_count=3, question_index=9, selected_option_index=0
        )


def test_quiz_run_complete_requires_every_active_question_answered_or_skipped():
    """The run-complete check — gating the score screen and retakes — must
    require every active question to be answered or skipped, not just some."""
    state = empty_quiz_state(generation=1, question_count=2)
    assert not quiz_run_complete(state)

    _, state = apply_quiz_answer(
        None, generation=1, question_count=2, question_index=0, selected_option_index=0
    )
    assert not quiz_run_complete(state)

    _, state = apply_quiz_skip(
        {"quiz_state": state}, generation=1, question_count=2, question_index=1
    )
    assert quiz_run_complete(state)
