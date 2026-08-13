"""Media path into Artifact: image / video / podcast.

Generation stays in podcasts / video graph / image tool; call ``record``
once the result is final. Images deliver straight to an Artifact; podcast
and video still record from their own row once it is READY.
"""

from __future__ import annotations

from app.artifacts.media.image.record import record as record_image
from app.artifacts.media.podcast.record import record as record_podcast
from app.artifacts.media.video.record import record as record_video

__all__ = [
    "record_image",
    "record_podcast",
    "record_video",
]
