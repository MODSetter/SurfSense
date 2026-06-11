"""The brief: the editable configuration a user approves before drafting.

A :class:`PodcastSpec` front-loads every decision that drives token or audio
cost (language, speakers, voices, style, target length) so the expensive
drafting and rendering steps run once against settled inputs. It is stored as
JSONB on the ``podcasts`` row and round-trips through the review API.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# A speaker count beyond this is almost never a real podcast and explodes the
# voice/turn-attribution space, so we reject it at the brief gate.
MAX_SPEAKERS = 6

# Long-form is a goal, but an open-ended upper bound invites runaway TTS bills.
# One day of audio is a generous ceiling that still blocks obvious mistakes.
MAX_DURATION_MINUTES = 24 * 60

# BCP-47 primary subtag plus optional region (e.g. ``en``, ``en-US``, ``pt-BR``).
# Kept deliberately permissive: the voice catalog, not the brief, decides which
# languages can actually be synthesised. Casing is normalised after matching.
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def normalize_language_tag(value: str) -> str:
    """Validate and canonicalise a BCP-47 tag (lowercased primary subtag).

    Shared with the generation layer so resolved and user-entered languages are
    normalised identically before they reach a :class:`PodcastSpec`.
    """
    cleaned = value.strip()
    if not _LANGUAGE_TAG.match(cleaned):
        raise ValueError(f"not a valid BCP-47 language tag: {value!r}")
    primary, _, rest = cleaned.partition("-")
    return primary.lower() if not rest else f"{primary.lower()}-{rest}"


class SpeakerRole(StrEnum):
    """How a speaker functions in the conversation, used to steer drafting."""

    HOST = "host"
    COHOST = "cohost"
    GUEST = "guest"
    EXPERT = "expert"
    NARRATOR = "narrator"


class PodcastStyle(StrEnum):
    """The conversational format the transcript should follow."""

    CONVERSATIONAL = "conversational"
    INTERVIEW = "interview"
    DEBATE = "debate"
    MONOLOGUE = "monologue"
    NARRATIVE = "narrative"


class SpeakerSpec(BaseModel):
    """One voice in the podcast: who they are and which TTS voice renders them.

    ``slot`` is the stable join key. Transcript turns reference a speaker by
    ``slot`` and the renderer resolves ``voice_id`` for that same slot, so the
    two never drift even if speakers are reordered in the brief.
    """

    model_config = ConfigDict(extra="forbid")

    slot: int = Field(..., ge=0, description="Stable index a transcript turn references")
    name: str = Field(..., min_length=1, max_length=120)
    role: SpeakerRole
    voice_id: str = Field(
        ...,
        min_length=1,
        description="Catalog voice id valid for the spec's language and provider",
    )

    @field_validator("name", "voice_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class DurationTarget(BaseModel):
    """The desired finished length as an inclusive minute range.

    Drafting aims for the midpoint and treats the bounds as soft guardrails;
    storing a range (rather than a point) keeps long-form expectations honest
    without pretending we can hit an exact runtime.
    """

    model_config = ConfigDict(extra="forbid")

    min_minutes: int = Field(..., ge=1, le=MAX_DURATION_MINUTES)
    max_minutes: int = Field(..., ge=1, le=MAX_DURATION_MINUTES)

    @model_validator(mode="after")
    def _check_order(self) -> DurationTarget:
        if self.max_minutes < self.min_minutes:
            raise ValueError("max_minutes must be >= min_minutes")
        return self

    @property
    def midpoint_minutes(self) -> float:
        """The runtime drafting should aim for within the range."""
        return (self.min_minutes + self.max_minutes) / 2


class PodcastSpec(BaseModel):
    """The full brief approved before any tokens or audio are spent."""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(..., description="BCP-47 tag, e.g. 'en', 'en-US', 'pt-BR'")
    style: PodcastStyle = PodcastStyle.CONVERSATIONAL
    speakers: list[SpeakerSpec] = Field(..., min_length=1, max_length=MAX_SPEAKERS)
    duration: DurationTarget
    focus: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional user steer for what the episode should emphasise",
    )

    @field_validator("language")
    @classmethod
    def _normalise_language(cls, value: str) -> str:
        return normalize_language_tag(value)

    @field_validator("focus")
    @classmethod
    def _blank_focus_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _check_speaker_slots(self) -> PodcastSpec:
        slots = [speaker.slot for speaker in self.speakers]
        if len(slots) != len(set(slots)):
            raise ValueError("speaker slots must be unique")
        return self

    @model_validator(mode="after")
    def _check_style_speakers(self) -> PodcastSpec:
        # One voice is what "monologue" means; letting extra speakers through
        # would force drafting to silently pick a winner.
        if self.style is PodcastStyle.MONOLOGUE and len(self.speakers) != 1:
            raise ValueError("a monologue has exactly one speaker")
        return self

    def speaker_for(self, slot: int) -> SpeakerSpec:
        """Return the speaker bound to ``slot`` or raise if none matches."""
        for speaker in self.speakers:
            if speaker.slot == slot:
                return speaker
        raise KeyError(f"no speaker for slot {slot}")
