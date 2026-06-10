"""Podcast generation lifecycle.

The status drives a guarded state machine. A podcast is proposed (``PENDING``),
gets a reviewable brief (``AWAITING_BRIEF``), is drafted into a transcript
(``DRAFTING`` → ``AWAITING_REVIEW``), then rendered to audio (``RENDERING`` →
``READY``). ``FAILED`` and ``CANCELLED`` are terminal. The Python enum is kept
in lockstep with the ``podcast_status`` Postgres type via its paired migration.
"""

from __future__ import annotations

from enum import StrEnum


class PodcastStatus(StrEnum):
    PENDING = "pending"
    AWAITING_BRIEF = "awaiting_brief"
    DRAFTING = "drafting"
    AWAITING_REVIEW = "awaiting_review"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Whether no further transition is possible from this state."""
        return self in _TERMINAL

    @property
    def is_gate(self) -> bool:
        """Whether this state waits on user input before proceeding."""
        return self in _GATES


_TERMINAL = frozenset({PodcastStatus.READY, PodcastStatus.FAILED, PodcastStatus.CANCELLED})
_GATES = frozenset({PodcastStatus.AWAITING_BRIEF, PodcastStatus.AWAITING_REVIEW})
