"""Media path into Artifact (cutover): image / video / podcast.

Blob helpers live in ``media/{kind}/storage.py``.
Generation stays in podcasts / video graph / image tool+routes;
call ``record`` after the legacy row is READY/success.
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
