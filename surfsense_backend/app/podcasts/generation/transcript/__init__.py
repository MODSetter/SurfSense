"""Transcript drafting: outline-first, long-form dialogue generation."""

from __future__ import annotations

from .config import TranscriptConfig
from .graph import build_transcript_graph
from .planning import Outline, OutlineSegment, SegmentDraft
from .state import TranscriptState

__all__ = [
    "Outline",
    "OutlineSegment",
    "SegmentDraft",
    "TranscriptConfig",
    "TranscriptState",
    "build_transcript_graph",
]
