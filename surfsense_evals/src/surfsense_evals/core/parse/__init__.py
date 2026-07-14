"""Parsers shared across suites: citations, MCQ envelopes, AI-SDK SSE."""

from __future__ import annotations

from .answer_letter import AnswerLetterResult, extract_answer_letter
from .citations import CITATION_REGEX, ChunkCitation, CitationToken, UrlCitation, parse_citations
from .freeform_answer import extract_freeform_answer
from .sse import SseEvent, iter_sse_events

__all__ = [
    "CITATION_REGEX",
    "CitationToken",
    "ChunkCitation",
    "UrlCitation",
    "parse_citations",
    "AnswerLetterResult",
    "extract_answer_letter",
    "extract_freeform_answer",
    "SseEvent",
    "iter_sse_events",
]
