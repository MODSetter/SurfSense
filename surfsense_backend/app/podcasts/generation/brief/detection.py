"""The language-detection reply shape, normalised to a safe tag or ``None``."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.podcasts.schemas import normalize_language_tag


class DetectedLanguage(BaseModel):
    """What the detector returns: a usable BCP-47 tag, or ``None`` when unsure.

    A malformed or non-language reply is coerced to ``None`` so a bad detection
    quietly defers to the rest of the resolution chain rather than poisoning the
    spec with an invalid tag.
    """

    language: str | None = None

    @field_validator("language")
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return normalize_language_tag(value)
        except ValueError:
            return None
