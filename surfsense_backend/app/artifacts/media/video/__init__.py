"""Video media → Artifact cutover."""

from __future__ import annotations

from app.artifacts.media.video.storage import open_stream, purge

__all__ = ["open_stream", "purge"]
