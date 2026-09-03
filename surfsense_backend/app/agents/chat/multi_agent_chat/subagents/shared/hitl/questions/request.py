"""Checkpoint-safe structured-question request and response validation."""

from __future__ import annotations

from langgraph.types import interrupt
from pydantic import ValidationError

from .contracts import (
    STRUCTURED_QUESTION_RESPONSE_ADAPTER,
    StructuredQuestion,
    StructuredQuestionInterrupt,
    StructuredQuestionRespond,
    StructuredQuestionResponse,
)


def request_structured_questions(
    prompt: StructuredQuestionInterrupt,
) -> StructuredQuestionResponse:
    """Pause before side effects and validate the exact preset response."""
    raw_response = interrupt(prompt.model_dump(mode="json"))
    if (
        isinstance(raw_response, dict)
        and isinstance(raw_response.get("decisions"), list)
        and len(raw_response["decisions"]) == 1
    ):
        raw_response = raw_response["decisions"][0]
    try:
        response = STRUCTURED_QUESTION_RESPONSE_ADAPTER.validate_python(raw_response)
    except ValidationError as exc:
        raise ValueError("Invalid structured-question response") from exc

    validate_structured_response(prompt, response)
    return response


def validate_structured_response(
    prompt: StructuredQuestionInterrupt,
    response: StructuredQuestionResponse,
) -> None:
    """Validate a response against the exact pending question definition."""
    if (
        response.preset_id != prompt.origin.preset_id
        or response.preset_version != prompt.origin.preset_version
    ):
        raise ValueError("Structured-question response targets a stale preset")
    if isinstance(response, StructuredQuestionRespond):
        _validate_answers(prompt, response)


def _validate_answers(
    prompt: StructuredQuestionInterrupt,
    response: StructuredQuestionRespond,
) -> None:
    questions = {question.id: question for question in prompt.questions}
    answers = {answer.question_id: answer for answer in response.answers}
    if len(answers) != len(response.answers):
        raise ValueError("Structured-question response contains duplicate questions")
    if set(answers) - set(questions):
        raise ValueError("Structured-question response contains unknown questions")

    missing_required = {
        question.id
        for question in prompt.questions
        if question.required and question.id not in answers
    }
    if missing_required:
        raise ValueError("Structured-question response omits required questions")
    for question_id, answer in answers.items():
        _validate_answer(questions[question_id], answer.option_ids, answer.text)


def _validate_answer(
    question: StructuredQuestion,
    option_ids: tuple[str, ...],
    text: str | None,
) -> None:
    if question.input_type == "free_text":
        if option_ids or (question.required and not (text and text.strip())):
            raise ValueError("Invalid free-text answer")
        return

    if text is not None:
        raise ValueError("Selection answers cannot contain free text")
    if not question.minimum_selections <= len(option_ids) <= question.maximum_selections:
        raise ValueError("Structured-question answer has the wrong cardinality")
    allowed = {option.id for option in question.options}
    if not set(option_ids) <= allowed:
        raise ValueError("Structured-question answer contains unknown options")


def selected_option_id(
    response: StructuredQuestionRespond,
    question_id: str,
) -> str:
    """Return the sole option for a validated single-select answer."""
    answer = next(
        (answer for answer in response.answers if answer.question_id == question_id),
        None,
    )
    if answer is None or len(answer.option_ids) != 1:
        raise ValueError(f"No single selection for question {question_id!r}")
    return answer.option_ids[0]


def is_cancelled(response: StructuredQuestionResponse) -> bool:
    return response.type == "cancel"


__all__ = [
    "is_cancelled",
    "request_structured_questions",
    "selected_option_id",
    "validate_structured_response",
]
