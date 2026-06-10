"""Celery tasks driving the podcast lifecycle across its user gates.

One task per async phase: propose the brief, draft the transcript, render the
audio. Each is enqueued by the API after it performs the guarded status
transition, and each pushes its result onto the row for the frontend to observe.
"""

from __future__ import annotations

from .brief import propose_brief_task
from .draft import draft_transcript_task
from .render import render_audio_task

__all__ = [
    "draft_transcript_task",
    "propose_brief_task",
    "render_audio_task",
]
