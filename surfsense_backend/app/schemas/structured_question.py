"""Closed wire contracts for domain-neutral structured-question interrupts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

MAX_QUESTIONS = 8
MAX_OPTIONS = 12


class StructuredQuestionOrigin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["preset"]
    preset_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9.-]+$")
    preset_version: int = Field(ge=1)


class StructuredQuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9.-]+$")
    label: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=600)
    preview_asset: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[a-z0-9.-]+(?:/[a-z0-9.-]+)*$",
    )


class StructuredQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9.-]+$")
    prompt: str = Field(min_length=1, max_length=300)
    input_type: Literal["single_select", "multi_select", "free_text"]
    presentation: Literal["list", "visual_cards"] = "list"
    required: bool = True
    minimum_selections: int = Field(default=1, ge=0, le=MAX_OPTIONS)
    maximum_selections: int = Field(default=1, ge=1, le=MAX_OPTIONS)
    options: tuple[StructuredQuestionOption, ...] = Field(
        default=(),
        max_length=MAX_OPTIONS,
    )

    @field_validator("options")
    @classmethod
    def validate_options(
        cls, value: tuple[StructuredQuestionOption, ...]
    ) -> tuple[StructuredQuestionOption, ...]:
        ids = [option.id for option in value]
        if len(ids) != len(set(ids)):
            raise ValueError("option IDs must be unique")
        return value


class StructuredQuestionInterrupt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["structured_question"] = "structured_question"
    version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=120)
    message: str | None = Field(default=None, max_length=500)
    origin: StructuredQuestionOrigin
    questions: tuple[StructuredQuestion, ...] = Field(
        min_length=1,
        max_length=MAX_QUESTIONS,
    )

    @field_validator("questions")
    @classmethod
    def validate_questions(
        cls, value: tuple[StructuredQuestion, ...]
    ) -> tuple[StructuredQuestion, ...]:
        ids = [question.id for question in value]
        if len(ids) != len(set(ids)):
            raise ValueError("question IDs must be unique")
        for question in value:
            if question.input_type == "free_text":
                if question.options:
                    raise ValueError("free-text questions cannot contain options")
                continue
            if not question.options:
                raise ValueError("selection questions must contain options")
            if question.minimum_selections > question.maximum_selections:
                raise ValueError("minimum selections cannot exceed maximum")
            if question.maximum_selections > len(question.options):
                raise ValueError("maximum selections exceeds available options")
            if (
                question.input_type == "single_select"
                and (
                    question.minimum_selections not in (0, 1)
                    or question.maximum_selections != 1
                )
            ):
                raise ValueError("single-select questions must select at most one option")
        return value


class StructuredQuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str = Field(min_length=1, max_length=64)
    option_ids: tuple[str, ...] = Field(default=(), max_length=MAX_OPTIONS)
    text: str | None = Field(default=None, max_length=4_000)

    @field_validator("option_ids")
    @classmethod
    def validate_distinct_options(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("option IDs must be unique")
        return value


class StructuredQuestionRespond(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["respond"]
    preset_id: str = Field(min_length=1, max_length=64)
    preset_version: int = Field(ge=1)
    tool_call_id: str | None = Field(default=None, min_length=1, max_length=200)
    interrupt_id: str | None = Field(default=None, min_length=1, max_length=200)
    answers: tuple[StructuredQuestionAnswer, ...] = Field(
        min_length=1,
        max_length=MAX_QUESTIONS,
    )


class StructuredQuestionCancel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["cancel"]
    preset_id: str = Field(min_length=1, max_length=64)
    preset_version: int = Field(ge=1)
    tool_call_id: str | None = Field(default=None, min_length=1, max_length=200)
    interrupt_id: str | None = Field(default=None, min_length=1, max_length=200)


StructuredQuestionResponse = Annotated[
    StructuredQuestionRespond | StructuredQuestionCancel,
    Field(discriminator="type"),
]
STRUCTURED_QUESTION_RESPONSE_ADAPTER = TypeAdapter(StructuredQuestionResponse)


__all__ = [
    "STRUCTURED_QUESTION_RESPONSE_ADAPTER",
    "StructuredQuestion",
    "StructuredQuestionAnswer",
    "StructuredQuestionCancel",
    "StructuredQuestionInterrupt",
    "StructuredQuestionOption",
    "StructuredQuestionOrigin",
    "StructuredQuestionRespond",
    "StructuredQuestionResponse",
]
