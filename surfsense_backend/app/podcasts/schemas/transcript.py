"""The transcript: ordered dialogue turns drafting produces for review.

A :class:`Transcript` is the reviewable artifact at the go/no-go gate and the
exact input the renderer turns into audio. Each turn names a speaker by the
``slot`` defined in the :class:`~app.podcasts.schemas.spec.PodcastSpec`, so the
renderer can resolve the right voice without re-attributing anything.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TranscriptTurn(BaseModel):
    """A single spoken line by one speaker.

    Drafting models (especially GPT-5-family) often decorate each turn with
    extra keys like ``speaker_name``, ``emotion`` or ``tone``. The renderer only
    needs ``speaker`` + ``text``, so unknown keys are ignored rather than
    rejected — otherwise one stray field would fail the whole segment parse.
    """

    model_config = ConfigDict(extra="ignore")

    speaker: int = Field(..., ge=0, description="The PodcastSpec speaker slot speaking")
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("turn text must not be blank")
        return cleaned


class Transcript(BaseModel):
    """The full ordered dialogue for an episode."""

    model_config = ConfigDict(extra="forbid")

    turns: list[TranscriptTurn] = Field(..., min_length=1)

    @property
    def word_count(self) -> int:
        """Total spoken words, used to estimate runtime against the brief."""
        return sum(len(turn.text.split()) for turn in self.turns)
