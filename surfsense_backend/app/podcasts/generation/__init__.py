"""Generation: the controlled graphs that produce a brief and a transcript.

``brief`` proposes a reviewable spec from deterministic defaults; ``transcript``
is the LLM-driven step, drafting long-form dialogue outline-first.
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
