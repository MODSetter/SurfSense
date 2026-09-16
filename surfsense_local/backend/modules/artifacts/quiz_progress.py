"""Bounded, generation-scoped quiz progress stored on the artifact's own
metadata column.

Ported from surfsense_web's per-user progress store, minus the per-user
layer: a local install has one user (see ArtifactDep), so state lives
directly at ``artifact_metadata["quiz_state"]`` instead of nested under a
user id. Regenerating a quiz bumps ``Artifact.generation`` (see
service.regenerate_artifact); a stored state from an older generation is
treated as absent rather than migrated, same as surfsense_web.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import HTTPException, status

from modules.artifacts.models import Artifact, ArtifactFileRole
from shared.config import get_storage_settings

QuizMode = Literal["all", "missed"]


def read_quiz_questions(artifact: Artifact) -> list[dict[str, Any]]:
    """The quiz's questions, for bounds-checking and scoring retakes."""
    file = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "quiz has no file yet")
    path = get_storage_settings().data_dir / file.storage_key
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "the quiz file is no longer readable"
        ) from error
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "malformed quiz")
    return questions


def _canonical_scope(question_count: int) -> list[int]:
    return list(range(max(0, question_count)))


def _valid_state(
    value: object, *, generation: int, question_count: int
) -> dict[str, object] | None:
    if not isinstance(value, dict) or type(value.get("generation")) is not int:
        return None
    if value["generation"] != generation:
        return None
    mode = value.get("mode")
    raw_scope = value.get("active_question_indices")
    raw_answers = value.get("answers")
    raw_skipped = value.get("skipped_question_indices")
    if mode not in ("all", "missed"):
        return None
    if (
        not isinstance(raw_scope, list)
        or not isinstance(raw_answers, dict)
        or not isinstance(raw_skipped, list)
    ):
        return None
    if (
        not raw_scope
        or len(raw_scope) > question_count
        or any(type(index) is not int for index in raw_scope)
        or raw_scope != sorted(set(raw_scope))
        or any(not 0 <= index < question_count for index in raw_scope)
    ):
        return None
    if mode == "all" and raw_scope != _canonical_scope(question_count):
        return None

    answers: dict[str, int] = {}
    for index in range(question_count):
        answer = raw_answers.get(str(index))
        if type(answer) is int and 0 <= answer <= 3:
            answers[str(index)] = answer
    if (
        any(type(index) is not int for index in raw_skipped)
        or raw_skipped != sorted(set(raw_skipped))
        or any(not 0 <= index < question_count for index in raw_skipped)
        or any(str(index) in answers for index in raw_skipped)
    ):
        return None
    return {
        "generation": generation,
        "mode": mode,
        "active_question_indices": list(raw_scope),
        "answers": answers,
        "skipped_question_indices": list(raw_skipped),
    }


def empty_quiz_state(*, generation: int, question_count: int) -> dict[str, object]:
    return {
        "generation": generation,
        "mode": "all",
        "active_question_indices": _canonical_scope(question_count),
        "answers": {},
        "skipped_question_indices": [],
    }


def sanitize_quiz_state(
    metadata: dict[str, Any] | None, *, generation: int, question_count: int
) -> dict[str, object]:
    state = _valid_state(
        (metadata or {}).get("quiz_state"),
        generation=generation,
        question_count=question_count,
    )
    return state or empty_quiz_state(generation=generation, question_count=question_count)


def quiz_run_complete(state: dict[str, object]) -> bool:
    answers = state["answers"]
    skipped = state["skipped_question_indices"]
    return all(
        str(index) in answers or index in skipped
        for index in state["active_question_indices"]
    )


def _with_state(
    metadata: dict[str, Any] | None, state: dict[str, object]
) -> dict[str, Any]:
    updated = dict(metadata) if isinstance(metadata, dict) else {}
    updated["quiz_state"] = state
    return updated


def apply_quiz_answer(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    question_count: int,
    question_index: int,
    selected_option_index: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    state = sanitize_quiz_state(
        metadata, generation=generation, question_count=question_count
    )
    if question_index not in state["active_question_indices"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "question_index is outside the active quiz run"
        )
    if not 0 <= selected_option_index <= 3:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "selected_option_index must be between 0 and 3",
        )
    if question_index in state["skipped_question_indices"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "question was already skipped; retake before answering it",
        )
    key = str(question_index)
    existing = state["answers"].get(key)
    if existing is not None and existing != selected_option_index:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "question was already answered; retake before changing it",
        )
    answers = {**state["answers"], key: selected_option_index}
    state = {**state, "answers": answers}
    return _with_state(metadata, state), state


def apply_quiz_skip(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    question_count: int,
    question_index: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    state = sanitize_quiz_state(
        metadata, generation=generation, question_count=question_count
    )
    if question_index not in state["active_question_indices"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "question_index is outside the active quiz run"
        )
    if str(question_index) in state["answers"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "question was already answered; retake before skipping it",
        )
    skipped = sorted({*state["skipped_question_indices"], question_index})
    state = {**state, "skipped_question_indices": skipped}
    return _with_state(metadata, state), state


def apply_quiz_retake(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    correct_option_indices: list[int],
    mode: QuizMode,
) -> tuple[dict[str, Any], dict[str, object]]:
    question_count = len(correct_option_indices)
    state = sanitize_quiz_state(
        metadata, generation=generation, question_count=question_count
    )
    if not quiz_run_complete(state):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "complete the current quiz run before retaking it"
        )

    if mode == "missed":
        scope = [
            index
            for index, correct in enumerate(correct_option_indices)
            if state["answers"].get(str(index)) != correct
        ]
        if not scope:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "there are no missed questions to retake"
            )
        answers = {
            key: value for key, value in state["answers"].items() if int(key) not in scope
        }
        skipped = [
            index for index in state["skipped_question_indices"] if index not in scope
        ]
    else:
        scope = _canonical_scope(question_count)
        answers = {}
        skipped = []

    state = {
        "generation": generation,
        "mode": mode,
        "active_question_indices": scope,
        "answers": answers,
        "skipped_question_indices": skipped,
    }
    return _with_state(metadata, state), state
