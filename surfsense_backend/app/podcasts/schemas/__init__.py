"""Pydantic shapes for the podcast brief and transcript."""

from __future__ import annotations

from .spec import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    normalize_language_tag,
)
from .transcript import Transcript, TranscriptTurn

__all__ = [
    "DurationTarget",
    "PodcastSpec",
    "PodcastStyle",
    "SpeakerRole",
    "SpeakerSpec",
    "Transcript",
    "TranscriptTurn",
    "normalize_language_tag",
]
