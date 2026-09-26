from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.artifacts.flashcard_progress import (
    read_flashcard_count,
    sanitize_flashcard_state,
)
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.quiz_progress import read_quiz_questions, sanitize_quiz_state
from modules.documents.models import DocumentStatus

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class StudioJobCreate(BaseModel):
    """A request to generate one artifact from a workspace's documents."""

    format: str
    document_ids: list[int]
    prompt: Prompt | None = None
    options: dict | None = None


class FormatRead(BaseModel):
    """A format the picker offers, and whether it is usable right now."""

    key: str
    label: str
    requires_model_types: list[str]
    available: bool
    unavailable_reason: str | None


class ArtifactFileRead(BaseModel):
    role: ArtifactFileRole
    mime_type: str
    size_bytes: int
    original_filename: str


class QuizStateRead(BaseModel):
    """A quiz run in progress: which questions are in scope, and how they
    were answered so far. Generation-scoped — see quiz_progress.py."""

    generation: int
    mode: Literal["all", "missed"]
    active_question_indices: list[int]
    answers: dict[str, int]
    skipped_question_indices: list[int]


QuestionIndex = Annotated[int, Field(strict=True, ge=0)]
OptionIndex = Annotated[int, Field(strict=True, ge=0, le=3)]


class QuizAnswerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_index: QuestionIndex
    selected_option_index: OptionIndex


class QuizSkipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_index: QuestionIndex


class QuizRetakeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["all", "missed"]


class FlashcardStateRead(BaseModel):
    """A flashcard deck's study progress: marks and shuffle order.
    Generation-scoped — see flashcard_progress.py."""

    generation: int
    marks: dict[str, Literal["good", "again"]]
    order: list[int]


CardIndex = Annotated[int, Field(strict=True, ge=0)]


class FlashcardMarkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    card_index: CardIndex
    mark: Literal["good", "again"] | None


class FlashcardOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    order: list[CardIndex]


class ArtifactRead(BaseModel):
    """An artifact and the state of its underlying ARTIFACT document."""

    id: int
    document_id: int
    format: str
    generation: int
    title: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, artifact: Artifact) -> "ArtifactRead":
        document = artifact.document
        return cls(
            id=artifact.id,
            document_id=artifact.document_id,
            format=artifact.format,
            generation=artifact.generation,
            title=document.title,
            status=document.status,
            error_message=document.error_message,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
        )


class ArtifactDetail(ArtifactRead):
    """One artifact, its rendered body, and its stored files."""

    content: str | None
    files: list[ArtifactFileRead]
    quiz_state: QuizStateRead | None = None
    flashcard_state: FlashcardStateRead | None = None

    @classmethod
    def of(cls, artifact: Artifact) -> "ArtifactDetail":
        base = ArtifactRead.of(artifact).model_dump()
        return cls(
            **base,
            content=artifact.document.content,
            files=[
                ArtifactFileRead(
                    role=file.role,
                    mime_type=file.mime_type,
                    size_bytes=file.size_bytes,
                    original_filename=file.original_filename,
                )
                for file in artifact.files
            ],
            quiz_state=_quiz_state(artifact),
            flashcard_state=_flashcard_state(artifact),
        )


def _quiz_state(artifact: Artifact) -> QuizStateRead | None:
    if artifact.format != "quiz" or not artifact.files:
        return None
    questions = read_quiz_questions(artifact)
    state = sanitize_quiz_state(
        artifact.artifact_metadata,
        generation=artifact.generation,
        question_count=len(questions),
    )
    return QuizStateRead(**state)


def _flashcard_state(artifact: Artifact) -> FlashcardStateRead | None:
    if artifact.format != "flashcards" or not artifact.files:
        return None
    card_count = read_flashcard_count(artifact)
    state = sanitize_flashcard_state(
        artifact.artifact_metadata,
        generation=artifact.generation,
        card_count=card_count,
    )
    return FlashcardStateRead(**state)
