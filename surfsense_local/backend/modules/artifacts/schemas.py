from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.artifacts.flashcard_progress import (
    read_flashcard_count,
    sanitize_flashcard_state,
)
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.quiz_progress import read_quiz_questions, sanitize_quiz_state
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.script_documents.spec import SpecKind, spec_kind
from modules.artifacts.script_documents.version import version_of
from modules.artifacts.studio_documents.recipe import shown_spec_kind, studio_made
from modules.documents.models import DocumentStatus
from modules.source_scope.schemas import SourceScope

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class StudioJobCreate(BaseModel):
    """A request to generate one artifact from a workspace's documents.

    `source_scope` is resolved on the server and recorded, so regenerate can
    re-resolve it. `document_ids` is the older explicit list, used only when no
    scope is sent.
    """

    format: str
    source_scope: SourceScope | None = None
    document_ids: list[int] | None = None
    prompt: Prompt | None = None
    options: dict | None = None


class RefineRequest(BaseModel):
    """What to change in a Word document or PDF; the whole spec is rewritten for it."""

    instruction: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class FormatRead(BaseModel):
    """A format the picker offers, and whether it is usable right now."""

    key: str
    label: str
    requires_model_types: list[str]
    available: bool
    unavailable_reason: str | None
    # The reason as a code the interface translates; the prose is its fallback.
    unavailable_code: str | None = None


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


class ArtifactVersionRead(BaseModel):
    """Which version of a document an artifact is; the list shows each root once."""

    root_id: int
    number: int
    parent_id: int | None


class RevisionCountsRead(BaseModel):
    changes: int
    comments: int


class RevisionRead(BaseModel):
    """What a revised copy's version came from and holds; counts are a Word version's."""

    derived_from_document_id: int | None
    source_name: str
    counts: RevisionCountsRead | None
    # Operations this version applied; None when it accepted or rejected all.
    applied: int | None


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
    # None for an artifact that keeps no spec and so has no versions.
    version: ArtifactVersionRead | None = None
    spec_kind: SpecKind | None = None
    # Whether Refine may rewrite this version: a ready Word or PDF Studio made.
    refinable: bool = False

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
            version=_version(artifact),
            spec_kind=shown_spec_kind(artifact.artifact_metadata),
            refinable=_refinable(artifact),
        )


class ArtifactDetail(ArtifactRead):
    """One artifact, its rendered body, and its stored files."""

    content: str | None
    files: list[ArtifactFileRead]
    quiz_state: QuizStateRead | None = None
    flashcard_state: FlashcardStateRead | None = None
    revision: RevisionRead | None = None

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
            revision=_revision(artifact),
        )


def _refinable(artifact: Artifact) -> bool:
    """The agent's own documents are edited in its chat (07, decision 8)."""
    meta = artifact.artifact_metadata
    return (
        artifact.document.status is DocumentStatus.READY
        and spec_kind(meta) is not None
        and studio_made(meta)
    )


def _version(artifact: Artifact) -> ArtifactVersionRead | None:
    version = version_of(artifact.artifact_metadata)
    if version is None:
        return None
    return ArtifactVersionRead(
        root_id=version.root, number=version.number, parent_id=version.parent
    )


def _revision(artifact: Artifact) -> RevisionRead | None:
    revision = revision_of(artifact.artifact_metadata)
    if revision is None:
        return None
    report = revision.get("report")
    return RevisionRead(
        derived_from_document_id=revision.get("derived_from_document_id"),
        source_name=revision["source_name"],
        counts=revision.get("counts"),
        applied=report["applied"] if report else None,
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
