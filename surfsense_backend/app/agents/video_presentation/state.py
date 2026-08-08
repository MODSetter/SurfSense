"""Define the state structures for the video presentation agent."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession


class SlideContent(BaseModel):
    """Represents a single parsed slide from content analysis."""

    slide_number: int = Field(..., description="1-based slide number")
    title: str = Field(..., description="Concise slide title")
    subtitle: str = Field(..., description="One-line subtitle or tagline")
    content_in_markdown: str = Field(
        ..., description="Slide body content formatted as markdown"
    )
    speaker_transcripts: list[str] = Field(
        ...,
        description="2-4 short sentences a presenter would say while this slide is shown",
    )
    background_explanation: str = Field(
        ...,
        description="Emotional mood and color direction for this slide",
    )


class PresentationSlides(BaseModel):
    """Represents the full set of parsed slides from the LLM."""

    language: str = Field(
        default="",
        description=(
            "BCP-47 tag of the language the slides and narration are written in "
            '(e.g. "en", "es", "ja", "pt-BR"). Empty when the model did not report one.'
        ),
    )
    slides: list[SlideContent] = Field(
        ..., description="Ordered array of presentation slides"
    )

    @field_validator("language", mode="before")
    @classmethod
    def _coerce_language(cls, value: object) -> str:
        """Drop a non-string language instead of failing the whole parse.

        Pydantic's smart mode rejects e.g. ``int`` for a ``str`` field, so without
        this a model that answered ``"language": 42`` would raise and take every
        slide down with it. Narration has a fallback chain; slide generation does
        not, so an unusable tag must degrade rather than abort.
        """
        return value if isinstance(value, str) else ""


class SlideAudioResult(BaseModel):
    """Audio generation result for a single slide."""

    slide_number: int
    audio_file: str = Field(..., description="Path to the per-slide audio file")
    duration_seconds: float = Field(..., description="Audio duration in seconds")
    duration_in_frames: int = Field(
        ..., description="Audio duration in frames (at 30fps)"
    )


class SlideSceneCode(BaseModel):
    """Generated Remotion component code for a single slide."""

    slide_number: int
    code: str = Field(
        ..., description="Raw Remotion React component source code for this slide"
    )
    title: str = Field(..., description="Short title for the composition")


@dataclass
class State:
    """State for the video presentation agent graph.

    Pipeline: parse slides → (TTS audio ∥ theme assignment) → generate Remotion code
    The frontend receives the slides + code + audio and handles compilation/rendering.
    """

    db_session: AsyncSession
    source_content: str

    slides: list[SlideContent] | None = None
    language: str | None = None
    slide_audio_results: list[SlideAudioResult] | None = None
    slide_theme_assignments: dict[int, tuple[str, str]] | None = None
    slide_scene_codes: list[SlideSceneCode] | None = None
