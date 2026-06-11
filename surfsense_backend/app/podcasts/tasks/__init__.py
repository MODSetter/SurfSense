"""Celery tasks driving the podcast lifecycle across its expensive phases.

One task per heavy async phase: draft the transcript (LLM) and render the audio
(TTS). The brief is deterministic and proposed inline at create time, so it has
no task. Each task is enqueued by the API after it performs the guarded status
transition, and each pushes its result onto the row for the frontend to observe.
"""

from __future__ import annotations

from .draft import draft_transcript_task
from .render import render_audio_task

__all__ = [
    "draft_transcript_task",
    "render_audio_task",
]
