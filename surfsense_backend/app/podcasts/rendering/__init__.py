"""Rendering: synthesise and merge an approved transcript into audio.

The :class:`PodcastRenderer` is the public entry point; the segment cache and
FFmpeg merge are implementation details it owns.
"""

from __future__ import annotations

from .errors import RenderError
from .renderer import PodcastRenderer, RenderedPodcast

__all__ = ["PodcastRenderer", "RenderError", "RenderedPodcast"]
