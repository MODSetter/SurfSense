"""Generation: the LLM-driven brief and transcript controlled graphs.

Two small graphs hold all the intelligence: ``brief`` proposes a reviewable spec
(language detection + resolution), and ``transcript`` drafts long-form dialogue
outline-first. Everything else in the podcast pipeline is deterministic.
"""

from __future__ import annotations

from .brief import BriefConfig, BriefState, build_brief_graph
from .transcript import TranscriptConfig, TranscriptState, build_transcript_graph

__all__ = [
    "BriefConfig",
    "BriefState",
    "TranscriptConfig",
    "TranscriptState",
    "build_brief_graph",
    "build_transcript_graph",
]
