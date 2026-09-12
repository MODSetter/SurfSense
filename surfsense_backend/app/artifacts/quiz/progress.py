"""Bounded, generation-scoped quiz progress stored per authenticated user."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

QuizMode = Literal["all", "missed"]
QuizQuestionIndex = Annotated[int, Field(strict=True, ge=0)]
QuizOptionIndex = Annotated[int, Field(strict=True, ge=0, le=3)]


class QuizAnswerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(strict=True, gt=0)
    question_index: QuizQuestionIndex
    selected_option_index: QuizOptionIndex


class QuizSkipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(strict=True, gt=0)
    question_index: QuizQuestionIndex


class QuizRetakeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(strict=True, gt=0)
    mode: QuizMode


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
    canonical = _canonical_scope(question_count)
    if mode == "all" and raw_scope != canonical:
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


def _progress_by_user(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    question_count: int,
) -> dict[str, dict[str, object]]:
    quiz = metadata.get("quiz") if isinstance(metadata, dict) else None
    raw_users = quiz.get("progress_by_user") if isinstance(quiz, dict) else None
    if not isinstance(raw_users, dict):
        return {}

    users: dict[str, dict[str, object]] = {}
    for user_key, raw_state in raw_users.items():
        if not isinstance(user_key, str):
            continue
        try:
            if str(UUID(user_key)) != user_key:
                continue
        except ValueError:
            continue
        state = _valid_state(
            raw_state,
            generation=generation,
            question_count=question_count,
        )
        if state is not None:
            users[user_key] = state
    return users


def empty_quiz_state(*, generation: int, question_count: int) -> dict[str, object]:
    return {
        "generation": generation,
        "mode": "all",
        "active_question_indices": _canonical_scope(question_count),
        "answers": {},
        "skipped_question_indices": [],
    }


def sanitize_quiz_state(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    question_count: int,
) -> dict[str, object]:
    state = _progress_by_user(
        metadata,
        generation=generation,
        question_count=question_count,
    ).get(str(user_id))
    return state or empty_quiz_state(
        generation=generation,
        question_count=question_count,
    )


def quiz_state_digest(state: dict[str, object]) -> str:
    canonical = json.dumps(
        state,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def quiz_run_complete(state: dict[str, object]) -> bool:
    answers = state["answers"]
    skipped = state["skipped_question_indices"]
    return all(
        str(index) in answers or index in skipped
        for index in state["active_question_indices"]
    )


def apply_quiz_answer(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    question_count: int,
    question_index: int,
    selected_option_index: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    users = _progress_by_user(
        metadata,
        generation=generation,
        question_count=question_count,
    )
    state = users.get(str(user_id)) or empty_quiz_state(
        generation=generation,
        question_count=question_count,
    )
    if question_index not in state["active_question_indices"]:
        raise ValueError("question_index is outside the active quiz run")
    if not 0 <= selected_option_index <= 3:
        raise ValueError("selected_option_index must be between 0 and 3")

    answers = dict(state["answers"])
    key = str(question_index)
    if question_index in state["skipped_question_indices"]:
        raise RuntimeError("question was already skipped; retake before answering it")
    existing = answers.get(key)
    if existing is not None and existing != selected_option_index:
        raise RuntimeError("question was already answered; retake before changing it")
    answers[key] = selected_option_index
    state = {**state, "answers": answers}
    users[str(user_id)] = state
    return _with_users(metadata, users), state


def apply_quiz_skip(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    question_count: int,
    question_index: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    users = _progress_by_user(
        metadata,
        generation=generation,
        question_count=question_count,
    )
    state = users.get(str(user_id)) or empty_quiz_state(
        generation=generation,
        question_count=question_count,
    )
    if question_index not in state["active_question_indices"]:
        raise ValueError("question_index is outside the active quiz run")
    if str(question_index) in state["answers"]:
        raise RuntimeError("question was already answered; retake before skipping it")

    skipped = sorted({*state["skipped_question_indices"], question_index})
    state = {**state, "skipped_question_indices": skipped}
    users[str(user_id)] = state
    return _with_users(metadata, users), state


def apply_quiz_retake(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    correct_option_indices: list[int],
    mode: QuizMode,
) -> tuple[dict[str, Any], dict[str, object]]:
    question_count = len(correct_option_indices)
    users = _progress_by_user(
        metadata,
        generation=generation,
        question_count=question_count,
    )
    state = users.get(str(user_id)) or empty_quiz_state(
        generation=generation,
        question_count=question_count,
    )
    if not quiz_run_complete(state):
        raise RuntimeError("complete the current quiz run before retaking it")

    answers = dict(state["answers"])
    skipped = list(state["skipped_question_indices"])
    if mode == "missed":
        scope = [
            index
            for index, correct in enumerate(correct_option_indices)
            if answers.get(str(index)) != correct
        ]
        if not scope:
            raise RuntimeError("there are no missed questions to retake")
        for index in scope:
            answers.pop(str(index), None)
        skipped = [index for index in skipped if index not in scope]
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
    users[str(user_id)] = state
    return _with_users(metadata, users), state


def _with_users(
    metadata: dict[str, Any] | None,
    users: dict[str, dict[str, object]],
) -> dict[str, Any]:
    updated = dict(metadata) if isinstance(metadata, dict) else {}
    if users:
        updated["quiz"] = {"progress_by_user": users}
    else:
        updated.pop("quiz", None)
    return updated
